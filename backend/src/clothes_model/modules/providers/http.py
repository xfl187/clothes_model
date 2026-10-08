"""Provider availability, redacted configuration, and validation HTTP API."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from clothes_model.core.features import feature_enabled, require_feature
from clothes_model.core.problems import AppProblem
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.modules.assets.domain import IdempotencyRecord
from clothes_model.modules.auth.application import VerifiedCredential
from clothes_model.modules.auth.http import AdminIdentity, require_admin, require_app
from clothes_model.modules.providers.application.ports import ProviderRegistryPort
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import (
    ProviderConfig,
    ProviderConfigRevision,
    ProviderError,
)

router = APIRouter(tags=["Providers"])
AppIdentity = Annotated[VerifiedCredential, Depends(require_app)]
Admin = Annotated[AdminIdentity, Depends(require_admin)]


class ProviderConfigBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=120)
    type: Literal["llm_image_edit", "comfyui", "unknown"]
    adapter_type: str = Field(min_length=1, max_length=96)
    endpoint: str = Field(min_length=1, max_length=512)
    model: str = Field(min_length=1, max_length=160)
    timeout_seconds: int = Field(ge=1, le=3600)
    api_key: str | None = None
    vendor_parameters: dict[str, object] = Field(default_factory=dict)


def _problem(
    status: int, code: str, detail: str, *, retryable: bool = False
) -> AppProblem:
    return AppProblem(status, code, "Provider 请求无法完成", detail, retryable=retryable)


def _service(request: Request) -> ProviderConfigService:
    registry: ProviderRegistryPort = request.app.state.provider_registry
    return ProviderConfigService(
        lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions),
        registry,
        request.app.state.secret_cipher,
    )


def _config_ref(config: ProviderConfig, revision: ProviderConfigRevision) -> dict[str, object]:
    return {
        "provider_id": config.id,
        "config_version_id": revision.id,
        "revision": revision.revision,
    }


def _capabilities(revision: ProviderConfigRevision) -> dict[str, object]:
    return json.loads(revision.capabilities_json)


def _config_dict(
    config: ProviderConfig, revision: ProviderConfigRevision
) -> dict[str, object]:
    return {
        "id": config.id,
        "display_name": config.display_name,
        "type": config.provider_type,
        "adapter_type": revision.adapter_type,
        "endpoint": revision.endpoint,
        "model": revision.model,
        "timeout_seconds": revision.timeout_seconds,
        "state": config.state,
        "secret_configured": config.secret_envelope is not None,
        "secret_updated_at": config.secret_updated_at,
        "config_ref": _config_ref(config, revision),
        "capabilities": _capabilities(revision),
        "updated_at": config.updated_at,
    }


async def _current_or_404(
    service: ProviderConfigService, provider_id: str
) -> tuple[ProviderConfig, ProviderConfigRevision]:
    config = await service.get(provider_id)
    revision = await service.current_revision(provider_id)
    if config is None or revision is None:
        raise _problem(404, "not_found", "Provider 配置不存在。")
    return config, revision


def _provider_enabled(request: Request, config: ProviderConfig) -> bool:
    return config.provider_type != "comfyui" or feature_enabled(request, "comfyui")


def _require_provider_enabled(request: Request, config: ProviderConfig) -> None:
    if config.provider_type == "comfyui":
        require_feature(request, "comfyui")


async def _enabled_current_or_404(
    request: Request, service: ProviderConfigService, provider_id: str
) -> tuple[ProviderConfig, ProviderConfigRevision]:
    config, revision = await _current_or_404(service, provider_id)
    _require_provider_enabled(request, config)
    return config, revision


def _body_parameters(body: ProviderConfigBody) -> dict[str, object]:
    return dict(body.vendor_parameters)


@router.get("/api/v1/providers", operation_id="listAvailableProviders")
async def list_available_providers(
    request: Request, identity: AppIdentity
) -> dict[str, object]:
    del identity
    service = _service(request)
    default = await service.get_default()
    default_provider_id = default.provider_id if default else None
    items: list[dict[str, object]] = []
    for config in await service.list():
        if not _provider_enabled(request, config):
            continue
        if config.state not in {"active", "validated"}:
            continue
        revision = await service.current_revision(config.id)
        if revision is None:
            continue
        assessment = await service.assess_availability_for(config, revision)
        availability = assessment.status
        items.append(
            {
                "id": config.id,
                "display_name": config.display_name,
                "type": config.provider_type,
                "availability": availability,
                "unavailable_reason": assessment.unavailable_reason,
                "is_default": config.id == default_provider_id,
                "config_ref": _config_ref(config, revision),
                "capabilities": _capabilities(revision),
            }
        )
    return {"items": items, "next_cursor": None, "has_more": False}


@router.get("/api/v1/admin/provider-configs", operation_id="listProviderConfigs")
async def list_provider_configs(request: Request, identity: Admin) -> dict[str, object]:
    del identity
    service = _service(request)
    items: list[dict[str, object]] = []
    for config in await service.list():
        if not _provider_enabled(request, config):
            continue
        revision = await service.current_revision(config.id)
        if revision is None:
            continue
        items.append(_config_dict(config, revision))
    return {"items": items, "next_cursor": None, "has_more": False}


@router.post(
    "/api/v1/admin/provider-configs", status_code=201, operation_id="createProviderConfig"
)
async def create_provider_config(
    request: Request,
    body: ProviderConfigBody,
    identity: Admin,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    if body.type == "comfyui":
        require_feature(request, "comfyui")
    request_digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    service = _service(request)
    try:
        async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
            existing = await uow.idempotency.get_bound(
                "admin", identity.token_id, "provider.create", key_digest
            )
        if existing is not None:
            if existing.request_digest != request_digest:
                raise _problem(409, "idempotency_key_reused", "幂等键已绑定到不同请求。")
            config, revision = await _enabled_current_or_404(
                request, service, str(existing.resource_id)
            )
            return _config_dict(config, revision)
        config = await service.create(
            display_name=body.display_name,
            provider_type=body.type,
            adapter_type=body.adapter_type,
            endpoint=body.endpoint,
            model=body.model,
            timeout_seconds=body.timeout_seconds,
            vendor_parameters=_body_parameters(body),
            api_key=body.api_key,
        )
        revision = await service.current_revision(config.id)
        assert revision is not None
        now = datetime.now(UTC)
        async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
            await uow.idempotency.add(
                _idempotency_record(
                    "admin",
                    identity.token_id,
                    "provider.create",
                    key_digest,
                    request_digest,
                    config.id,
                    now,
                )
            )
            await uow.commit()
        return _config_dict(config, revision)
    except ProviderError as error:
        raise _problem(409, error.code, error.detail, retryable=error.retryable) from error


def _idempotency_record(
    actor_scope: str,
    actor_id: str,
    operation: str,
    key_digest: str,
    request_digest: str,
    resource_id: str,
    now: datetime,
) -> IdempotencyRecord:
    return IdempotencyRecord(
        id=str(uuid4()),
        actor_scope=actor_scope,
        actor_id=actor_id,
        operation=operation,
        key_digest=key_digest,
        request_digest=request_digest,
        state="completed",
        response_status=201,
        resource_id=resource_id,
        created_at=now,
        expires_at=now + timedelta(days=1),
    )


@router.get(
    "/api/v1/admin/provider-configs/{provider_id}", operation_id="getProviderConfig"
)
async def get_provider_config(
    request: Request, provider_id: str, identity: Admin
) -> dict[str, object]:
    del identity
    config, revision = await _enabled_current_or_404(request, _service(request), provider_id)
    return _config_dict(config, revision)


@router.patch(
    "/api/v1/admin/provider-configs/{provider_id}", operation_id="updateProviderConfig"
)
async def update_provider_config(
    request: Request,
    provider_id: str,
    body: ProviderConfigBody,
    identity: Admin,
) -> dict[str, object]:
    del identity
    service = _service(request)
    current, _ = await _current_or_404(service, provider_id)
    _require_provider_enabled(request, current)
    if body.type == "comfyui":
        require_feature(request, "comfyui")
    try:
        config = await service.update(
            provider_id,
            display_name=body.display_name,
            provider_type=body.type,
            adapter_type=body.adapter_type,
            endpoint=body.endpoint,
            model=body.model,
            timeout_seconds=body.timeout_seconds,
            vendor_parameters=_body_parameters(body),
            api_key=body.api_key,
        )
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail, retryable=error.retryable) from error
    revision = await service.current_revision(config.id)
    assert revision is not None
    return _config_dict(config, revision)


@router.delete(
    "/api/v1/admin/provider-configs/{provider_id}",
    status_code=204,
    operation_id="deleteProviderConfig",
)
async def delete_provider_config(
    request: Request, provider_id: str, identity: Admin
) -> Response:
    del identity
    config, _ = await _current_or_404(_service(request), provider_id)
    _require_provider_enabled(request, config)
    try:
        await _service(request).delete(provider_id)
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail) from error
    return Response(status_code=204)


async def _lifecycle_response(
    service: ProviderConfigService, config: ProviderConfig
) -> dict[str, object]:
    revision = await service.current_revision(config.id)
    assert revision is not None
    return _config_dict(config, revision)


@router.post(
    "/api/v1/admin/provider-configs/{provider_id}/archive",
    operation_id="archiveProviderConfig",
)
async def archive_provider_config(
    request: Request,
    provider_id: str,
    identity: Admin,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del identity, idempotency_key
    service = _service(request)
    config, _ = await _current_or_404(service, provider_id)
    _require_provider_enabled(request, config)
    try:
        config = await service.archive(provider_id)
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail) from error
    return await _lifecycle_response(service, config)


@router.post(
    "/api/v1/admin/provider-configs/{provider_id}/restore",
    operation_id="restoreProviderConfig",
)
async def restore_provider_config(
    request: Request,
    provider_id: str,
    identity: Admin,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del identity, idempotency_key
    service = _service(request)
    config, _ = await _current_or_404(service, provider_id)
    _require_provider_enabled(request, config)
    try:
        config = await service.restore(provider_id)
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail) from error
    return await _lifecycle_response(service, config)


@router.post(
    "/api/v1/admin/provider-configs/{provider_id}/validate",
    operation_id="validateProviderConfig",
)
async def validate_provider_config(
    request: Request,
    provider_id: str,
    identity: Admin,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del identity, idempotency_key
    service = _service(request)
    await _enabled_current_or_404(request, service, provider_id)
    try:
        outcome = await service.validate(provider_id)
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail) from error
    return {
        "status": outcome.status,
        "checked_at": datetime.now(UTC),
        "steps": [
            {"key": step.key, "status": step.status, "detail": step.detail}
            for step in outcome.steps
        ],
        "capabilities": outcome.capabilities.to_payload(),
    }


@router.post(
    "/api/v1/admin/provider-configs/{provider_id}/connection-test",
    operation_id="testProviderConnection",
)
async def test_provider_connection(
    request: Request,
    provider_id: str,
    identity: Admin,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del identity, idempotency_key
    service = _service(request)
    await _enabled_current_or_404(request, service, provider_id)
    try:
        outcome = await service.connection_test(provider_id)
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail) from error
    return {
        "status": outcome.status,
        "checked_at": datetime.now(UTC),
        "steps": [
            {"key": step.key, "status": step.status, "detail": step.detail}
            for step in outcome.steps
        ],
    }


@router.post(
    "/api/v1/admin/provider-configs/{provider_id}/enable",
    operation_id="enableProviderConfig",
)
async def enable_provider_config(
    request: Request,
    provider_id: str,
    identity: Admin,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del identity, idempotency_key
    service = _service(request)
    await _enabled_current_or_404(request, service, provider_id)
    try:
        config = await service.enable(provider_id)
    except ProviderError as error:
        status = 404 if error.code == "provider_not_found" else 409
        raise _problem(status, error.code, error.detail) from error
    revision = await service.current_revision(config.id)
    assert revision is not None
    return _config_dict(config, revision)


__all__ = ["router"]
