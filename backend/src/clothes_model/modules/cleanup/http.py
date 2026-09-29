"""Administrative storage cleanup boundary."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from clothes_model.generated.models import CleanupRequest
from clothes_model.modules.auth.http import AdminIdentity, require_admin
from clothes_model.modules.cleanup.service import run_local_first_cleanup

router = APIRouter(tags=["Storage"])


@router.post("/api/v1/admin/storage/cleanup", operation_id="cleanupStorage")
async def cleanup_storage(
    request: Request,
    body: CleanupRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del body, identity, idempotency_key
    result = await run_local_first_cleanup(
        request.app.state.database.sessions, request.app.state.storage
    )
    return {
        "deleted_files": result.deleted_files,
        "reclaimed_bytes": result.reclaimed_bytes,
        "skipped_protected_files": result.skipped_protected_files,
        "completed_at": datetime.now(UTC),
    }
