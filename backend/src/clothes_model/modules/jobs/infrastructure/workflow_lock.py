"""Shared Comfy Workflow locking used by job creation paths.

Returns ``None`` for non-Comfy adapters so LLM jobs stay Workflow-free.
"""

import json
from collections.abc import Mapping
from typing import cast

from sqlalchemy import select

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db


class WorkflowLockError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _as_mapping(value: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _as_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


async def lock_active_workflow(
    uow: SqlAlchemyUnitOfWork,
    *,
    adapter_type: str,
    vendor_parameters_json: str,
    garment_asset_id: str,
    mask_asset_id: str | None,
    candidate_count: int,
) -> tuple[str, str] | None:
    if adapter_type != "comfyui":
        return None
    active = await uow.workflows.get_active("precise_try_on")
    if active is None:
        raise WorkflowLockError("workflow_not_active", "当前没有可用的换装 Workflow。")
    locked_revision_workflow = _as_mapping(
        json.loads(vendor_parameters_json or "{}")
    ).get("workflow_version_id")
    if locked_revision_workflow != active.id:
        raise WorkflowLockError("workflow_incompatible", "Provider 配置与当前 Workflow 不一致。")
    manifest = _as_mapping(json.loads(active.manifest_json or "{}"))
    capabilities = _as_mapping(manifest.get("capabilities"))
    bindings = _as_mapping(manifest.get("bindings"))
    category = await uow.session.scalar(
        select(db.garment_assets.c.category).where(
            db.garment_assets.c.asset_id == garment_asset_id
        )
    )
    allowed = _as_mapping(capabilities.get("garment_categories")).get("values")
    if isinstance(allowed, list) and allowed and category not in allowed:
        raise WorkflowLockError("workflow_incompatible", "该衣物类别不被当前 Workflow 支持。")
    requires_mask = "mask" in bindings
    if requires_mask != (mask_asset_id is not None):
        raise WorkflowLockError("workflow_incompatible", "遮罩输入与 Workflow 要求不一致。")
    max_candidates = _as_int(
        _as_mapping(capabilities.get("output_constraints")).get("max_candidates"), 1
    )
    if candidate_count > max_candidates:
        raise WorkflowLockError("workflow_incompatible", "当前 Workflow 不支持该候选数量。")
    snapshot = {
        "workflow_version_id": active.id,
        "workflow_id": active.workflow_id,
        "version": active.version,
        "mode": active.mode,
        "workflow_sha256": active.workflow_sha256,
        "manifest_sha256": active.manifest_sha256,
        "bindings_schema_version": active.bindings_schema_version,
        "bindings": bindings,
        "capabilities": capabilities,
    }
    return active.id, json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
