"""Restart-safe cleanup of acknowledged local-first input copies."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db

TERMINAL_JOB_STATES = ("succeeded", "partially_succeeded", "failed", "cancelled")


class StoragePort(Protocol):
    def delete(self, relative_path: str) -> None: ...


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    deleted_files: int = 0
    reclaimed_bytes: int = 0
    skipped_protected_files: int = 0


async def schedule_eligible_assets(sessions: object, *, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    deadline = current + timedelta(hours=24)
    async with SqlAlchemyUnitOfWork(sessions) as uow:  # type: ignore[arg-type]
        active_job_ref = (
            select(db.asset_references.c.id)
            .select_from(
                db.asset_references.join(
                    db.jobs,
                    (db.asset_references.c.source_kind == "job")
                    & (db.asset_references.c.source_id == db.jobs.c.id),
                )
            )
            .where(
                db.asset_references.c.asset_id == db.assets.c.id,
                db.asset_references.c.active.is_(True),
                ~db.jobs.c.state.in_(TERMINAL_JOB_STATES),
            )
            .exists()
        )
        result = cast(
            CursorResult[Any],
            await uow.session.execute(
                update(db.assets)
                .where(
                    db.assets.c.kind.in_(["person", "garment"]),
                    db.assets.c.content_state == "available",
                    db.assets.c.durable_client_copy_confirmed.is_(True),
                    db.assets.c.cleanup_after.is_(None),
                    ~active_job_ref,
                )
                .values(cleanup_after=deadline, updated_at=current)
            ),
        )
        await uow.commit()
        return int(result.rowcount or 0)


async def cleanup_due_assets(
    sessions: object, storage: StoragePort, *, now: datetime | None = None
) -> CleanupSummary:
    current = now or datetime.now(UTC)
    deleted_files = reclaimed_bytes = skipped = 0
    async with SqlAlchemyUnitOfWork(sessions) as uow:  # type: ignore[arg-type]
        rows = (
            (
                await uow.session.execute(
                    select(
                        db.assets.c.id,
                        db.assets.c.stored_object_id,
                        db.stored_objects.c.relative_path,
                        db.stored_objects.c.size_bytes,
                    )
                    .select_from(db.assets.join(db.stored_objects))
                    .where(
                        db.assets.c.kind.in_(["person", "garment"]),
                        db.assets.c.content_state == "available",
                        db.assets.c.durable_client_copy_confirmed.is_(True),
                        db.assets.c.cleanup_after.is_not(None),
                        db.assets.c.cleanup_after <= current,
                    )
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            active = await uow.session.scalar(
                select(db.asset_references.c.id)
                .select_from(
                    db.asset_references.join(
                        db.jobs,
                        (db.asset_references.c.source_kind == "job")
                        & (db.asset_references.c.source_id == db.jobs.c.id),
                    )
                )
                .where(
                    db.asset_references.c.asset_id == row["id"],
                    db.asset_references.c.active.is_(True),
                    ~db.jobs.c.state.in_(TERMINAL_JOB_STATES),
                )
                .limit(1)
            )
            if active is not None:
                skipped += 1
                await uow.session.execute(
                    update(db.assets).where(db.assets.c.id == row["id"]).values(cleanup_after=None)
                )
                await uow.commit()
                continue
            await uow.session.execute(
                update(db.assets)
                .where(
                    db.assets.c.id == row["id"],
                    db.assets.c.cleanup_after <= current,
                    db.assets.c.durable_client_copy_confirmed.is_(True),
                )
                .values(
                    stored_object_id=None,
                    content_state="deleted",
                    deleted_at=current,
                    cleanup_after=None,
                    updated_at=current,
                )
            )
            await uow.commit()
            remaining = await uow.session.scalar(
                select(db.stored_objects.c.asset_ref_count).where(
                    db.stored_objects.c.id == row["stored_object_id"]
                )
            )
            if remaining == 0:
                storage.delete(str(row["relative_path"]))
                await uow.session.execute(
                    delete(db.stored_objects).where(
                        db.stored_objects.c.id == row["stored_object_id"]
                    )
                )
                await uow.commit()
                deleted_files += 1
                reclaimed_bytes += int(row["size_bytes"])
    return CleanupSummary(deleted_files, reclaimed_bytes, skipped)


async def run_local_first_cleanup(
    sessions: object, storage: StoragePort, *, now: datetime | None = None
) -> CleanupSummary:
    await schedule_eligible_assets(sessions, now=now)
    return await cleanup_due_assets(sessions, storage, now=now)


def _active_reference_exists() -> Any:
    return (
        select(db.asset_references.c.id)
        .select_from(
            db.asset_references.join(
                db.jobs,
                (db.asset_references.c.source_kind == "job")
                & (db.asset_references.c.source_id == db.jobs.c.id),
            )
        )
        .where(
            db.asset_references.c.asset_id == db.assets.c.id,
            db.asset_references.c.active.is_(True),
            ~db.jobs.c.state.in_(TERMINAL_JOB_STATES),
        )
        .exists()
    )


async def get_retention_policy(sessions: object) -> tuple[int, int]:
    async with SqlAlchemyUnitOfWork(sessions) as uow:  # type: ignore[arg-type]
        row = (
            await uow.session.execute(
                select(
                    db.retention_policy.c.unfavorited_output_days,
                    db.retention_policy.c.intermediate_file_days,
                )
            )
        ).one_or_none()
    if row is None:
        return 30, 7
    return int(row[0]), int(row[1])


async def update_retention_policy(
    sessions: object,
    *,
    unfavorited_output_days: int,
    intermediate_file_days: int,
    now: datetime | None = None,
) -> tuple[int, int]:
    current = now or datetime.now(UTC)
    async with SqlAlchemyUnitOfWork(sessions) as uow:  # type: ignore[arg-type]
        existing = await uow.session.scalar(
            select(db.retention_policy.c.id).where(db.retention_policy.c.id == "default")
        )
        if existing is None:
            await uow.session.execute(
                db.retention_policy.insert().values(
                    id="default",
                    unfavorited_output_days=unfavorited_output_days,
                    intermediate_file_days=intermediate_file_days,
                    updated_at=current,
                )
            )
        else:
            await uow.session.execute(
                update(db.retention_policy)
                .where(db.retention_policy.c.id == "default")
                .values(
                    unfavorited_output_days=unfavorited_output_days,
                    intermediate_file_days=intermediate_file_days,
                    updated_at=current,
                )
            )
        await uow.commit()
    return unfavorited_output_days, intermediate_file_days


async def _reclaimable_rows(uow: SqlAlchemyUnitOfWork, current: datetime) -> list[Any]:
    output_days, intermediate_days = await get_retention_policy_from(uow)
    output_deadline = current - timedelta(days=output_days)
    intermediate_deadline = current - timedelta(days=intermediate_days)
    result = await uow.session.execute(
        select(
            db.assets.c.id,
            db.assets.c.stored_object_id,
            db.stored_objects.c.relative_path,
            db.stored_objects.c.size_bytes,
        )
        .select_from(db.assets.join(db.stored_objects))
        .where(
            db.assets.c.content_state == "available",
            db.assets.c.favorite.is_(False),
            db.assets.c.kind.in_(["generated_output", "mask"]),
            ~_active_reference_exists(),
            (
                (
                    (db.assets.c.kind == "generated_output")
                    & (db.assets.c.created_at < output_deadline)
                )
                | (
                    (db.assets.c.kind == "mask")
                    & (db.assets.c.created_at < intermediate_deadline)
                )
            ),
        )
    )
    return list(result.mappings().all())


async def get_retention_policy_from(uow: SqlAlchemyUnitOfWork) -> tuple[int, int]:
    row = (
        await uow.session.execute(
            select(
                db.retention_policy.c.unfavorited_output_days,
                db.retention_policy.c.intermediate_file_days,
            )
        )
    ).one_or_none()
    if row is None:
        return 30, 7
    return int(row[0]), int(row[1])


async def scan_storage(
    sessions: object,
    *,
    actor_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    async with SqlAlchemyUnitOfWork(sessions) as uow:  # type: ignore[arg-type]
        rows = await _reclaimable_rows(uow, current)
        protected = int(
            await uow.session.scalar(
                select(func.count())
                .select_from(db.assets)
                .where(
                    db.assets.c.content_state == "available",
                    db.assets.c.kind.in_(["generated_output", "mask"]),
                    (db.assets.c.favorite.is_(True)) | _active_reference_exists(),
                )
            )
            or 0
        )
        scan_id = str(uuid4())
        reclaimable_bytes = sum(int(row["size_bytes"]) for row in rows)
        await uow.session.execute(
            db.storage_scans.insert().values(
                id=scan_id,
                reclaimable_files=len(rows),
                reclaimable_bytes=reclaimable_bytes,
                protected_files=protected,
                actor_id=actor_id,
                created_at=current,
            )
        )
        await uow.commit()
    return {
        "scan_id": scan_id,
        "reclaimable_files": len(rows),
        "reclaimable_bytes": reclaimable_bytes,
        "protected_files": protected,
        "completed_at": current,
    }


async def cleanup_scanned(
    sessions: object,
    storage: StoragePort,
    *,
    scan_id: str,
    now: datetime | None = None,
) -> CleanupSummary | None:
    current = now or datetime.now(UTC)
    async with SqlAlchemyUnitOfWork(sessions) as uow:  # type: ignore[arg-type]
        scan = await uow.session.scalar(
            select(db.storage_scans.c.id).where(db.storage_scans.c.id == scan_id)
        )
        if scan is None:
            return None
        rows = await _reclaimable_rows(uow, current)
        deleted_files = reclaimed_bytes = 0
        for row in rows:
            await uow.session.execute(
                update(db.assets)
                .where(db.assets.c.id == row["id"], db.assets.c.content_state == "available")
                .values(
                    stored_object_id=None,
                    content_state="deleted",
                    deleted_at=current,
                    cleanup_after=None,
                    updated_at=current,
                )
            )
            await uow.commit()
            remaining = await uow.session.scalar(
                select(db.stored_objects.c.asset_ref_count).where(
                    db.stored_objects.c.id == row["stored_object_id"]
                )
            )
            if remaining == 0:
                storage.delete(str(row["relative_path"]))
                await uow.session.execute(
                    delete(db.stored_objects).where(
                        db.stored_objects.c.id == row["stored_object_id"]
                    )
                )
                await uow.commit()
                deleted_files += 1
                reclaimed_bytes += int(row["size_bytes"])
    return CleanupSummary(deleted_files, reclaimed_bytes, 0)
