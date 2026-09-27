import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from clothes_model.core.problems import AppProblem
from clothes_model.generated.models import DefaultProviderUpdateRequest
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules._stub import StubRoute, add_stub_routes
from clothes_model.modules.auth.http import AdminIdentity, require_admin
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


add_stub_routes(
    router,
    (
        StubRoute("/api/v1/admin/configuration/comfy-node", "GET", "getComfyNodeConfiguration"),
        StubRoute("/api/v1/admin/configuration/comfy-node", "PUT", "updateComfyNodeConfiguration"),
        StubRoute(
            "/api/v1/admin/configuration/comfy-node/test",
            "POST",
            "testComfyNodeConnection",
        ),
        StubRoute("/api/v1/admin/configuration/retention", "GET", "getRetentionPolicy"),
        StubRoute("/api/v1/admin/configuration/retention", "PUT", "updateRetentionPolicy"),
        StubRoute("/api/v1/admin/storage/scan", "POST", "scanStorage"),
        StubRoute("/api/v1/admin/diagnostics/jobs", "GET", "listDiagnosticJobs"),
        StubRoute("/api/v1/admin/diagnostics/jobs/{job_id}", "GET", "getDiagnosticJob"),
    ),
)


@router.get("/api/v1/admin/storage", operation_id="getStorageStatus")
async def storage_status(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    usage = shutil.disk_usage(request.app.state.storage.root)
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        temporary = await uow.session.scalar(
            select(func.coalesce(func.sum(db.upload_sessions.c.confirmed_offset), 0)).where(
                db.upload_sessions.c.state.in_(("created", "uploading"))
            )
        )
    reserve = request.app.state.settings.storage_reserve_bytes
    return {
        "capacity_bytes": usage.total,
        "available_bytes": usage.free,
        "reserved_bytes": reserve,
        "temporary_bytes": int(temporary or 0),
        "accepting_uploads": usage.free > reserve,
    }
