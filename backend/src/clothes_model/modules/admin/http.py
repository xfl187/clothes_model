import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules._stub import StubRoute, add_stub_routes
from clothes_model.modules.auth.http import AdminIdentity, require_admin

router = APIRouter(tags=["Admin", "Diagnostics"])
add_stub_routes(
    router,
    (
        StubRoute(
            "/api/v1/admin/configuration/default-provider",
            "GET",
            "getDefaultProviderConfiguration",
        ),
        StubRoute(
            "/api/v1/admin/configuration/default-provider",
            "PUT",
            "updateDefaultProviderConfiguration",
        ),
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
