"""Administrative storage cleanup boundary."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from clothes_model.core.problems import AppProblem
from clothes_model.generated.models import CleanupRequest
from clothes_model.modules.auth.http import AdminIdentity, require_admin
from clothes_model.modules.cleanup.service import cleanup_scanned, run_local_first_cleanup

router = APIRouter(tags=["Storage"])


@router.post("/api/v1/admin/storage/cleanup", operation_id="cleanupStorage")
async def cleanup_storage(
    request: Request,
    body: CleanupRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    scanned = await cleanup_scanned(
        request.app.state.database.sessions,
        request.app.state.storage,
        scan_id=str(body.scan_id.root),
    )
    if scanned is None:
        raise AppProblem(
            409,
            "scan_not_found",
            "扫描记录无效",
            "请先执行扫描预览，再使用返回的 scan_id 清理。",
        )
    input_result = await run_local_first_cleanup(
        request.app.state.database.sessions, request.app.state.storage
    )
    del identity
    return {
        "deleted_files": scanned.deleted_files + input_result.deleted_files,
        "reclaimed_bytes": scanned.reclaimed_bytes + input_result.reclaimed_bytes,
        "skipped_protected_files": input_result.skipped_protected_files,
        "completed_at": datetime.now(UTC),
    }
