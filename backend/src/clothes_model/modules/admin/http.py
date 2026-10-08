import base64
import hashlib
import json
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import and_, or_, select

from clothes_model.core.features import feature_enabled, require_feature
from clothes_model.core.problems import AppProblem
from clothes_model.generated.models import (
    ComfyNodeConfigurationRequest,
    DefaultProviderUpdateRequest,
    RetentionPolicyUpdateRequest,
)
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules.assets.domain import IdempotencyRecord
from clothes_model.modules.auth.http import AdminIdentity, require_admin
from clothes_model.modules.cleanup.service import (
    get_retention_policy,
    scan_storage,
    update_retention_policy,
)
from clothes_model.modules.comfy.application import ComfyNodeError, ComfyNodeService
from clothes_model.modules.comfy.domain import LOGICAL_COMFY_PROVIDER_ID, ComfyNodeConfig
from clothes_model.modules.jobs.payloads import job_payload
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import ProviderError

router = APIRouter(tags=["Admin", "Diagnostics"])


def _provider_service(request: Request) -> ProviderConfigService:
    return ProviderConfigService(
        lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions),
        request.app.state.provider_registry,
        request.app.state.secret_cipher,
    )


def _default_problem(code: str, detail: str) -> AppProblem:
    return AppProblem(409, code, "默认 Provider 无法更新", detail)


def _provider_label(snapshot_json: str) -> str:
    decoded: object = json.loads(snapshot_json or "{}")
    if isinstance(decoded, dict):
        label = cast(Mapping[str, object], decoded).get("label")
        if isinstance(label, str):
            return label
    return "Provider"


def _comfy_service(request: Request) -> ComfyNodeService:
    settings = request.app.state.settings
    return ComfyNodeService(
        lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions),
        request.app.state.secret_cipher,
        request.app.state.comfy_http_client,
        environment=settings.environment,
        allowed_hosts=tuple(settings.comfy_node_allowed_hosts),
    )


def _comfy_problem(error: ComfyNodeError) -> AppProblem:
    return AppProblem(error.status, error.code, "ComfyUI 节点操作失败", error.detail)


def _comfy_payload(
    config: ComfyNodeConfig, active_workflow_compatibility: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "endpoint": config.endpoint,
        "logical_provider_id": LOGICAL_COMFY_PROVIDER_ID,
        "timeout_seconds": config.timeout_seconds,
        "enabled": config.enabled,
        "credential_configured": config.credential_envelope is not None,
        "credential_updated_at": config.credential_updated_at,
        "health": config.health_status,
        "health_detail": config.health_detail,
        "observed_server_version": config.observed_server_version,
        "active_workflow_compatibility": active_workflow_compatibility,
        "last_checked_at": config.last_checked_at,
        "updated_at": config.updated_at,
    }


async def _active_workflow_compatibility(
    request: Request, config: ComfyNodeConfig
) -> dict[str, object]:
    if config.health_status == "offline":
        state = "offline"
    elif config.health_status == "incompatible":
        state = "incompatible"
    else:
        async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
            active = await uow.session.scalar(
                select(db.workflow_versions.c.id).where(
                    db.workflow_versions.c.state == "active",
                    db.workflow_versions.c.mode == "precise_try_on",
                )
            )
        if active is None:
            state = "unchecked"
        elif config.health_status == "healthy":
            state = "compatible"
        else:
            state = "unknown"
    return {"status": state, "checked_at": datetime.now(UTC), "checks": []}


@router.get(
    "/api/v1/admin/configuration/default-provider",
    operation_id="getDefaultProviderConfiguration",
)
async def get_default_provider(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    service = _provider_service(request)
    selection = await service.get_default()
    if selection is None:
        raise _default_problem("default_provider_not_set", "默认 Provider 尚未设置。")
    config = await service.get(selection.provider_id)
    if config is None or (
        config.provider_type == "comfyui" and not feature_enabled(request, "comfyui")
    ):
        raise _default_problem("default_provider_not_set", "当前版本没有可用的默认 Provider。")
    revision = await service.current_revision(selection.provider_id)
    if revision is None:
        raise _default_problem("default_provider_not_set", "默认 Provider 配置缺失。")
    return {
        "provider_id": selection.provider_id,
        "config_ref": {
            "provider_id": selection.provider_id,
            "config_version_id": revision.id,
            "revision": revision.revision,
        },
        "updated_at": selection.updated_at,
    }


@router.put(
    "/api/v1/admin/configuration/default-provider",
    operation_id="updateDefaultProviderConfiguration",
)
async def update_default_provider(
    request: Request,
    body: DefaultProviderUpdateRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    service = _provider_service(request)
    config = await service.get(str(body.provider_id.root))
    if config is not None and config.provider_type == "comfyui":
        require_feature(request, "comfyui")
    try:
        selection = await service.set_default(str(body.provider_id.root))
    except ProviderError as error:
        raise _default_problem(error.code, error.detail) from error
    revision = await service.current_revision(selection.provider_id)
    if revision is None:
        raise _default_problem("default_provider_not_set", "默认 Provider 配置缺失。")
    return {
        "provider_id": selection.provider_id,
        "config_ref": {
            "provider_id": selection.provider_id,
            "config_version_id": revision.id,
            "revision": revision.revision,
        },
        "updated_at": selection.updated_at,
    }


@router.get(
    "/api/v1/admin/configuration/retention",
    operation_id="getRetentionPolicy",
)
async def get_retention(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    days = await get_retention_policy(request.app.state.database.sessions)
    return {
        "unfavorited_output_days": days[0],
        "intermediate_file_days": days[1],
        "updated_at": datetime.now(UTC),
    }


@router.put(
    "/api/v1/admin/configuration/retention",
    operation_id="updateRetentionPolicy",
)
async def update_retention(
    request: Request,
    body: RetentionPolicyUpdateRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    days = await update_retention_policy(
        request.app.state.database.sessions,
        unfavorited_output_days=int(body.unfavorited_output_days),
        intermediate_file_days=int(body.intermediate_file_days),
    )
    return {
        "unfavorited_output_days": days[0],
        "intermediate_file_days": days[1],
        "updated_at": datetime.now(UTC),
    }


@router.post("/api/v1/admin/storage/scan", operation_id="scanStorage")
async def scan_storage_route(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    del idempotency_key
    return await scan_storage(
        request.app.state.database.sessions, actor_id=identity.session_id
    )


@router.get(
    "/api/v1/admin/configuration/comfy-node",
    operation_id="getComfyNodeConfiguration",
)
async def get_comfy_node(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    require_feature(request, "comfyui")
    config = await _comfy_service(request).get()
    if config is None:
        raise AppProblem(404, "comfy_node_not_configured", "节点尚未配置", "请先保存节点配置。")
    return _comfy_payload(config, await _active_workflow_compatibility(request, config))


@router.put(
    "/api/v1/admin/configuration/comfy-node",
    operation_id="updateComfyNodeConfiguration",
)
async def update_comfy_node(
    request: Request,
    body: ComfyNodeConfigurationRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    require_feature(request, "comfyui")
    try:
        config = await _comfy_service(request).update(
            endpoint=str(body.endpoint),
            timeout_seconds=body.timeout_seconds,
            enabled=body.enabled,
            credential=body.credential,
            actor_id=identity.session_id,
        )
    except ComfyNodeError as error:
        raise _comfy_problem(error) from error
    return _comfy_payload(config, await _active_workflow_compatibility(request, config))


@router.post(
    "/api/v1/admin/configuration/comfy-node/test",
    operation_id="testComfyNodeConnection",
)
async def test_comfy_node(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    require_feature(request, "comfyui")
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    request_digest = hashlib.sha256(b"comfy-node-test-v1").hexdigest()
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        existing = await uow.idempotency.get_bound(
            "admin", identity.token_id, "comfy_node.test", key_digest
        )
    if existing is not None:
        if existing.request_digest != request_digest:
            raise AppProblem(
                409,
                "idempotency_key_reused",
                "幂等键冲突",
                "该幂等键已绑定到不同请求。",
            )
        return cast(dict[str, object], json.loads(existing.response_body or "{}"))
    try:
        _, result = await _comfy_service(request).probe(actor_id=identity.session_id)
    except ComfyNodeError as error:
        raise _comfy_problem(error) from error
    timestamp = datetime.now(UTC)
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        await uow.idempotency.add(
            IdempotencyRecord(
                id=str(uuid4()),
                actor_scope="admin",
                actor_id=identity.token_id,
                operation="comfy_node.test",
                key_digest=key_digest,
                request_digest=request_digest,
                state="completed",
                response_status=200,
                response_body=json.dumps(result, default=str, separators=(",", ":")),
                resource_id="default",
                created_at=timestamp,
                expires_at=timestamp + timedelta(hours=24),
            )
        )
        await uow.commit()
    return result


@router.get("/api/v1/admin/diagnostics/jobs", operation_id="listDiagnosticJobs")
async def list_diagnostic_jobs(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    limit: int = Query(50, ge=1, le=100),
    state: str | None = None,
    cursor: str | None = None,
) -> dict[str, object]:
    del identity
    statement = (
        select(db.jobs)
        .order_by(db.jobs.c.created_at.desc(), db.jobs.c.id.desc())
        .limit(limit + 1)
    )
    if state is not None:
        statement = statement.where(db.jobs.c.state == state)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            marker_time, marker_id = decoded
            statement = statement.where(
                or_(
                    db.jobs.c.created_at < marker_time,
                    and_(
                        db.jobs.c.created_at == marker_time,
                        db.jobs.c.id < marker_id,
                    ),
                )
            )
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        rows = (await uow.session.execute(statement)).mappings().all()
        has_more = len(rows) > limit
        page = rows[:limit]
        items: list[dict[str, object]] = []
        for row in page:
            items_count = len(await uow.jobs.list_items(str(row["id"])))
            items.append(
                {
                    "job_id": row["id"],
                    "state": row["state"],
                    "provider_label": _provider_label(str(row["provider_snapshot_json"])),
                    "item_count": max(1, items_count),
                    "updated_at": row["updated_at"],
                }
            )
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = _encode_cursor(last["created_at"], str(last["id"]))
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "snapshot_at": datetime.now(UTC),
    }


def _encode_cursor(created_at: object, job_id: str) -> str:
    raw = f"{created_at}|{job_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode()
        created_text, _, job_id = raw.partition("|")
        return datetime.fromisoformat(created_text), job_id
    except (ValueError, UnicodeDecodeError):
        return None


@router.get("/api/v1/admin/diagnostics/jobs/{job_id}", operation_id="getDiagnosticJob")
async def get_diagnostic_job(
    request: Request,
    job_id: str,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        job = await uow.jobs.get_job(job_id)
        if job is None:
            raise AppProblem(404, "not_found", "任务不存在", "诊断对象不存在。")
        payload = await job_payload(uow, job)
        events = await uow.job_events.list_events(job_id)
        redacted = [
            {
                "at": event.occurred_at,
                "category": event.event_type,
                "conclusion": event.to_state or "recorded",
            }
            for event in events
        ]
    return {
        "job": payload,
        "snapshot_at": datetime.now(UTC),
        "redacted_external_events": redacted,
    }


@router.get("/api/v1/admin/storage", operation_id="getStorageStatus")
async def storage_status(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    usage = shutil.disk_usage(request.app.state.storage.root)
    reserve = request.app.state.settings.storage_reserve_bytes
    accepting = usage.free > reserve
    used = usage.total - usage.free
    return {
        "state": "healthy" if accepting else "blocked",
        "capacity_bytes": usage.total,
        "used_bytes": used,
        "available_bytes": usage.free,
        "accepting_new_work": accepting,
        "block_reason": None if accepting else "storage_capacity",
        "checked_at": datetime.now(UTC),
    }
