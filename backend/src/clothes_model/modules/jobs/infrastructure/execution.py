"""Durable job execution through the provider port with private output persistence."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import BinaryIO, Protocol
from uuid import uuid4

from sqlalchemy import insert, select, update

from clothes_model.core.logging import get_logger
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.infrastructure.storage.local import NormalizedImage
from clothes_model.modules.jobs.domain import (
    Job,
    JobExecutionEvent,
    JobItem,
    aggregate_state,
    backoff_seconds,
)
from clothes_model.modules.providers.application.ports import ProviderRegistryPort
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import (
    ProviderError,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
)

logger = get_logger(__name__)

MAX_TRANSIENT_ATTEMPTS = 3
MAX_POLL_QUERIES = 5


class StoragePort(Protocol):
    def normalize_and_store(self, source: bytes) -> NormalizedImage: ...

    def open(self, relative_path: str) -> BinaryIO: ...


class JobExecutionService:
    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        provider_service: ProviderConfigService,
        registry: ProviderRegistryPort,
        storage: StoragePort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._provider_service = provider_service
        self._registry = registry
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(self, item_id: str, claimant_token: str) -> None:
        try:
            await self._execute(item_id, claimant_token)
        except Exception:
            logger.exception(
                "job_item_execution_failed", extra={"event_data": {"item_id": item_id}}
            )

    async def _execute(self, item_id: str, claimant_token: str) -> None:
        async with self._uow_factory() as uow:
            item = await uow.jobs.get_item(item_id)
            job = await uow.jobs.get_job(item.job_id) if item is not None else None
        if item is None or job is None or item.claimant_token != claimant_token:
            return

        invocation, _, _ = await self._provider_service.resolve_invocation(
            job.provider_id, job.provider_revision_id
        )
        adapter = self._registry.resolve(invocation.adapter_type)

        try:
            person_bytes, garment_bytes = await self._inputs(item, job)
        except FileNotFoundError:
            await self._fail(item_id, "input_unavailable", "输入素材不可用。")
            return

        if not await self._compare_and_set(
            item_id, ("queued", "waiting_provider"), "preparing", block_reason=None
        ):
            return
        await self._record_event(job.id, item_id, "preparing", "queued", "preparing")

        request = ProviderRequest(
            job_item_id=item_id,
            candidate_index=item.candidate_index,
            candidate_count=job.candidate_count,
            seed=job.seed,
            person_bytes=person_bytes,
            garment_bytes=garment_bytes,
        )
        try:
            submission = await adapter.submit(invocation, request)
        except ProviderError as error:
            await self._handle_error(item, job, error)
            return

        await self._compare_and_set(
            item_id,
            ("preparing",),
            "running",
            external_execution_id=submission.external_execution_id,
        )
        await self._record_event(job.id, item_id, "running", "preparing", "running")

        for _ in range(MAX_POLL_QUERIES):
            try:
                status = await adapter.query(invocation, submission.external_execution_id)
            except ProviderError as error:
                await self._handle_error(item, job, error)
                return
            if status.state == "running":
                continue
            if status.state == "failed":
                if status.error is not None:
                    await self._handle_error(item, job, status.error)
                else:
                    await self._fail(item_id, "provider_failure", "生成失败。")
                return
            await self._persist_success(item, job, invocation, submission.external_execution_id)
            return

    async def _handle_error(self, item: JobItem, job: Job, error: ProviderError) -> None:
        now = self._clock()
        if error.error_class == "temporarily_offline":
            await self._compare_and_set(
                item.id,
                ("queued", "waiting_provider", "preparing", "running"),
                "waiting_provider",
                block_reason="provider_offline",
                updated_at=now,
            )
            await self._release(item.id)
        elif error.error_class == "retryable_transient":
            attempts = item.transient_attempts + 1
            if attempts < MAX_TRANSIENT_ATTEMPTS:
                await self._compare_and_set(
                    item.id,
                    ("preparing", "running"),
                    "queued",
                    block_reason="retry_backoff",
                    transient_attempts=attempts,
                    next_attempt_at=now + timedelta(seconds=backoff_seconds(attempts)),
                    updated_at=now,
                )
                await self._release(item.id)
            else:
                await self._fail_item(
                    item.id, "provider_retry_exhausted", "临时故障重试次数已耗尽。"
                )
        elif error.error_class == "externally_ambiguous":
            await self._attention(item.id, "external_state_unknown")
        elif error.error_class == "invalid_configuration":
            await self._attention(item.id, "configuration_invalid")
        else:
            await self._fail_item(item.id, error.code, error.detail)
        await self._recompute(job.id)

    async def _persist_success(
        self, item: JobItem, job: Job, invocation: ProviderInvocation, external_id: str
    ) -> None:
        adapter = self._registry.resolve(invocation.adapter_type)
        outputs = await adapter.fetch_outputs(invocation, external_id)
        now = self._clock()
        async with self._uow_factory() as uow:
            for output in outputs:
                normalized = self._store(output.content)
                await self._register_output(uow, item, normalized, output, now)
            await uow.commit()
        await self._compare_and_set(item.id, ("running",), "succeeded", updated_at=now)
        await self._release(item.id)
        await self._recompute(job.id)

    def _store(self, content: bytes) -> NormalizedImage:
        return self._storage.normalize_and_store(content)

    async def _register_output(
        self,
        uow: SqlAlchemyUnitOfWork,
        item: JobItem,
        normalized: NormalizedImage,
        output: ProviderOutput,
        now: datetime,
    ) -> None:
        sha256 = normalized.sha256
        relative_path = normalized.relative_path
        content_type = normalized.content_type
        size_bytes = normalized.size_bytes
        width = normalized.width
        height = normalized.height
        object_row = (
            await uow.session.execute(
                select(db.stored_objects).where(db.stored_objects.c.sha256 == sha256)
            )
        ).mappings().one_or_none()
        object_id = object_row["id"] if object_row else str(uuid4())
        if object_row is None:
            await uow.session.execute(
                insert(db.stored_objects).values(
                    id=object_id,
                    sha256=sha256,
                    relative_path=relative_path,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    width=width,
                    height=height,
                    state="available",
                    asset_ref_count=0,
                    created_at=now,
                    verified_at=now,
                )
            )
        asset_id = str(uuid4())
        await uow.session.execute(
            insert(db.assets).values(
                id=asset_id,
                kind="generated_output",
                stored_object_id=object_id,
                favorite=False,
                content_state="available",
                created_at=now,
                updated_at=now,
            )
        )
        await uow.session.execute(
            insert(db.generated_outputs).values(
                id=str(uuid4()),
                job_item_id=item.id,
                asset_id=asset_id,
                favorite=False,
                seed=output.seed,
                actual_parameters_json=json.dumps(
                    output.actual_parameters, separators=(",", ":"), sort_keys=True
                ),
                quality_warnings_json="[]",
                created_at=now,
            )
        )
        await uow.session.execute(
            insert(db.asset_references).values(
                id=str(uuid4()),
                asset_id=asset_id,
                source_kind="generated_output",
                source_id=item.id,
                display_label="生成结果",
                active=True,
                created_at=now,
            )
        )

    async def _inputs(self, item: JobItem, job: Job) -> tuple[bytes, bytes]:
        async with self._uow_factory() as uow:
            person = await self._read(uow, item.person_asset_id)
            garment = await self._read(uow, job.garment_asset_id)
        return person, garment

    async def _read(self, uow: SqlAlchemyUnitOfWork, asset_id: str) -> bytes:
        row = (
            await uow.session.execute(
                select(db.stored_objects.c.relative_path)
                .select_from(
                    db.assets.join(
                        db.stored_objects, db.assets.c.stored_object_id == db.stored_objects.c.id
                    )
                )
                .where(db.assets.c.id == asset_id, db.assets.c.content_state == "available")
            )
        ).scalar_one_or_none()
        if row is None:
            raise FileNotFoundError(asset_id)
        handle = self._storage.open(str(row))
        with handle as stream:
            return stream.read()

    async def _compare_and_set(
        self,
        item_id: str,
        expected: tuple[str, ...],
        state: str,
        **values: object,
    ) -> bool:
        values.setdefault("updated_at", self._clock())
        async with self._uow_factory() as uow:
            changed = await uow.jobs.compare_and_set_item_state(item_id, expected, state, values)
            await uow.commit()
        return changed

    async def _release(self, item_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.jobs.release_claim(item_id)
            await uow.commit()

    async def _fail(self, item_id: str, code: str, detail: str) -> None:
        await self._fail_item(item_id, code, detail)

    async def _fail_item(self, item_id: str, code: str, detail: str) -> None:
        now = self._clock()
        async with self._uow_factory() as uow:
            item = await uow.jobs.get_item(item_id)
            if item is None:
                return
            error = json.dumps(
                {
                    "type": f"https://clothes-model.local/problems/{code}",
                    "title": "生成失败",
                    "status": 502,
                    "code": code,
                    "detail": detail,
                    "trace_id": "",
                    "retryable": False,
                    "field_errors": [],
                    "context": {},
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            await uow.jobs.compare_and_set_item_state(
                item_id,
                ("queued", "waiting_provider", "preparing", "running", "needs_attention"),
                "failed",
                {"error_code": code, "error_json": error, "updated_at": now},
            )
            await uow.jobs.release_claim(item_id)
            await uow.commit()
        await self._recompute(item.job_id)

    async def _attention(self, item_id: str, block_reason: str) -> None:
        now = self._clock()
        async with self._uow_factory() as uow:
            await uow.jobs.compare_and_set_item_state(
                item_id,
                ("queued", "waiting_provider", "preparing", "running"),
                "needs_attention",
                {"block_reason": block_reason, "updated_at": now},
            )
            await uow.jobs.release_claim(item_id)
            await uow.commit()

    async def _record_event(
        self, job_id: str, item_id: str, event_type: str, from_state: str, to_state: str
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.job_events.add_event(
                _event(job_id, item_id, event_type, from_state, to_state, self._clock())
            )
            await uow.commit()

    async def _recompute(self, job_id: str) -> None:
        now = self._clock()
        async with self._uow_factory() as uow:
            job = await uow.jobs.get_job(job_id)
            items = await uow.jobs.list_items(job_id)
            if job is None or not items:
                return
            latest: dict[int, JobItem] = {}
            for item in items:
                current = latest.get(item.candidate_index)
                if current is None or item.attempt > current.attempt:
                    latest[item.candidate_index] = item
            state = aggregate_state(item.state for item in latest.values())
            block_reason = None
            if state == "waiting_provider":
                block_reason = "provider_offline"
            elif state == "needs_attention":
                block_reason = "external_state_unknown"
            updated = Job(
                id=job.id,
                mode=job.mode,
                state=state,
                candidate_count=job.candidate_count,
                garment_asset_id=job.garment_asset_id,
                provider_id=job.provider_id,
                provider_revision_id=job.provider_revision_id,
                provider_snapshot_json=job.provider_snapshot_json,
                block_reason=block_reason,
                blocked_detail=job.blocked_detail,
                seed=job.seed,
                advanced_parameters_json=job.advanced_parameters_json,
                mask_asset_id=job.mask_asset_id,
                related_job_id=job.related_job_id,
                workflow_version_id=job.workflow_version_id,
                workflow_snapshot_json=job.workflow_snapshot_json,
                next_attempt_at=job.next_attempt_at,
                created_at=job.created_at,
                updated_at=now,
            )
            await update_job(uow, updated)
            await uow.commit()


async def update_job(uow: SqlAlchemyUnitOfWork, job: Job) -> None:
    await uow.session.execute(
        update(db.jobs)
        .where(db.jobs.c.id == job.id)
        .values(
            state=job.state,
            block_reason=job.block_reason,
            blocked_detail=job.blocked_detail,
            next_attempt_at=job.next_attempt_at,
            updated_at=job.updated_at,
        )
    )


def _event(
    job_id: str, item_id: str, event_type: str, from_state: str, to_state: str, now: datetime
) -> JobExecutionEvent:
    return JobExecutionEvent(
        id=str(uuid4()),
        job_id=job_id,
        job_item_id=item_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        detail_json="{}",
        occurred_at=now,
    )
