"""Contract-shaped serialization for jobs, items, and generated outputs."""

import json
from typing import cast

from sqlalchemy import select

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules.jobs.domain import Job, JobItem


def _error(value: str | None) -> dict[str, object] | None:
    if not value:
        return None
    decoded: object = json.loads(value)
    return cast(dict[str, object], decoded) if isinstance(decoded, dict) else None


async def output_payload(
    uow: SqlAlchemyUnitOfWork, output_id: str
) -> dict[str, object] | None:
    row = (
        (
            await uow.session.execute(
                select(
                    db.generated_outputs,
                    db.assets.c.favorite.label("asset_favorite"),
                    db.assets.c.content_state.label("asset_content_state"),
                )
                .select_from(
                    db.generated_outputs.join(
                        db.assets, db.generated_outputs.c.asset_id == db.assets.c.id
                    )
                )
                .where(db.generated_outputs.c.id == output_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "job_item_id": row["job_item_id"],
        "asset_id": row["asset_id"],
        "favorite": bool(row["asset_favorite"]),
        "content_available": row["asset_content_state"] == "available",
        "seed": row["seed"],
        "actual_parameters": json.loads(row["actual_parameters_json"] or "{}"),
        "quality_warnings": json.loads(row["quality_warnings_json"] or "[]"),
        "created_at": row["created_at"],
    }


async def item_payload(uow: SqlAlchemyUnitOfWork, item: JobItem) -> dict[str, object]:
    outputs = await uow.job_outputs.list_outputs(item.id)
    output_payloads: list[dict[str, object]] = []
    for output in outputs:
        serialized = await output_payload(uow, output.id)
        if serialized is not None:
            output_payloads.append(serialized)
    payload: dict[str, object] = {
        "id": item.id,
        "job_id": item.job_id,
        "person_asset_id": item.person_asset_id,
        "candidate_index": item.candidate_index,
        "state": item.state,
        "attempt": item.attempt,
        "retry_of_job_item_id": item.retry_of_job_item_id,
        "superseded_by_job_item_id": item.superseded_by_job_item_id,
        "external_execution_id": item.external_execution_id,
        "next_attempt_at": item.next_attempt_at,
        "outputs": output_payloads,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
    if item.block_reason is not None:
        payload["block_reason"] = item.block_reason
    error = _error(item.error_json)
    if error is not None:
        payload["error"] = error
    return payload


async def _revision_number(uow: SqlAlchemyUnitOfWork, revision_id: str) -> int:
    value = await uow.session.scalar(
        select(db.provider_config_revisions.c.revision).where(
            db.provider_config_revisions.c.id == revision_id
        )
    )
    return int(value or 1)


async def job_payload(uow: SqlAlchemyUnitOfWork, job: Job) -> dict[str, object]:
    person_inputs = await uow.jobs.list_person_inputs(job.id)
    items = await uow.jobs.list_items(job.id)
    snapshot: object = json.loads(job.provider_snapshot_json or "{}")
    payload: dict[str, object] = {
        "id": job.id,
        "person_asset_ids": [entry.person_asset_id for entry in person_inputs],
        "garment_asset_id": job.garment_asset_id,
        "mode": job.mode,
        "generation_options": {
            "candidate_count": job.candidate_count,
            "seed": job.seed,
            "advanced_parameters": json.loads(job.advanced_parameters_json or "{}"),
        },
        "state": job.state,
        "provider_config_ref": {
            "provider_id": job.provider_id,
            "config_version_id": job.provider_revision_id,
            "revision": await _revision_number(uow, job.provider_revision_id),
        },
        "provider_snapshot": snapshot if isinstance(snapshot, dict) else {"label": "Provider"},
        "items": [await item_payload(uow, item) for item in items],
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.mask_asset_id is not None:
        payload["mask_asset_id"] = job.mask_asset_id
    if job.related_job_id is not None:
        payload["related_job_id"] = job.related_job_id
    if job.block_reason is not None:
        payload["block_reason"] = job.block_reason
    if job.blocked_detail is not None:
        payload["blocked_detail"] = job.blocked_detail
    if job.next_attempt_at is not None:
        payload["next_attempt_at"] = job.next_attempt_at
    if job.workflow_version_id is not None:
        workflow_snapshot: object = json.loads(job.workflow_snapshot_json or "{}")
        payload["workflow_version_ref"] = {"workflow_version_id": job.workflow_version_id}
        payload["workflow_snapshot"] = (
            workflow_snapshot if isinstance(workflow_snapshot, dict) else {"label": "Workflow"}
        )
    return payload
