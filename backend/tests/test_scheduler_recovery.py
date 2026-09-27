import asyncio
import io
import itertools
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.scheduler import JobScheduler
from clothes_model.infrastructure.storage import LocalFileStorage
from clothes_model.modules.assets.domain import Asset, GarmentMetadata, PersonMetadata, StoredObject
from clothes_model.modules.jobs.domain import Job, JobItem
from clothes_model.modules.jobs.infrastructure.execution import JobExecutionService
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
    ProviderStatusResult,
    ProviderSubmission,
)
from clothes_model.modules.providers.infrastructure import FakeImageEditAdapter, ProviderRegistry

_counter = itertools.count(1)


def _png() -> bytes:
    value = next(_counter)
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), (value % 256, (value * 5) % 256, (value * 11) % 256)).save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


class CountingAdapter(FakeImageEditAdapter):
    adapter_type = "counting_image_edit"

    def __init__(self, state: dict[str, object]) -> None:
        super().__init__()
        self._state = state
        self.submits = 0
        self.fetches = 0

    async def availability(self, invocation: ProviderInvocation) -> str:
        return str(self._state.get("availability", "available"))

    async def submit(
        self, invocation: ProviderInvocation, request: ProviderRequest
    ) -> ProviderSubmission:
        self.submits += 1
        self._state["blocked"] = bool(self._state.get("block_after_submit", False))
        return ProviderSubmission(
            state="accepted", external_execution_id=f"ext-{request.job_item_id}"
        )

    async def query(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> ProviderStatusResult:
        return ProviderStatusResult(state=str(self._state.get("query_state", "succeeded")))

    async def fetch_outputs(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> list[ProviderOutput]:
        self.fetches += 1
        return [ProviderOutput(content=_png(), content_type="image/png")]


class _Env:
    def __init__(self, tmp_path: Path) -> None:
        self.database_url = f"sqlite+aiosqlite:///{(tmp_path / 'recovery.db').as_posix()}"
        upgrade_database(self.database_url, tmp_path / "migration.lock")
        self.runtime = create_database_runtime(self.database_url, 5000)
        self.storage = LocalFileStorage(tmp_path / "storage")
        self.state: dict[str, object] = {"availability": "available", "query_state": "succeeded"}
        self.adapter = CountingAdapter(self.state)
        registry = ProviderRegistry([self.adapter], environment="test")
        self.registry = registry
        self.provider_service = ProviderConfigService(
            lambda: SqlAlchemyUnitOfWork(self.runtime.sessions), registry, None
        )

    def execution(self) -> JobExecutionService:
        return JobExecutionService(
            lambda: SqlAlchemyUnitOfWork(self.runtime.sessions),
            self.provider_service,
            self.registry,
            self.storage,
            capacity=lambda: not bool(self.state.get("blocked", False)),
        )

    def scheduler(self, execution: JobExecutionService) -> JobScheduler:
        return JobScheduler(
            self.runtime.sessions,
            execution,
            capacity=lambda: not bool(self.state.get("blocked", False)),
        )

    def close(self) -> None:
        asyncio.run(self.runtime.close())

    async def seed(
        self,
        *,
        state: str = "queued",
        block_reason: str | None = None,
        external_execution_id: str | None = None,
    ) -> dict[str, str]:
        person = self.storage.normalize_and_store(_png())
        garment = self.storage.normalize_and_store(_png())
        provider_id, revision_id = str(uuid4()), str(uuid4())
        person_id, garment_id, job_id, item_id = (str(uuid4()) for _ in range(4))
        person_object_id, garment_object_id = str(uuid4()), str(uuid4())
        now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
        async with SqlAlchemyUnitOfWork(self.runtime.sessions) as uow:
            await uow.stored_objects.add(
                StoredObject(
                    id=person_object_id,
                    sha256=person.sha256,
                    relative_path=person.relative_path,
                    content_type="image/jpeg",
                    size_bytes=person.size_bytes,
                    width=person.width,
                    height=person.height,
                    state="available",
                    asset_ref_count=0,
                    created_at=now,
                )
            )
            await uow.stored_objects.add(
                StoredObject(
                    id=garment_object_id,
                    sha256=garment.sha256,
                    relative_path=garment.relative_path,
                    content_type="image/jpeg",
                    size_bytes=garment.size_bytes,
                    width=garment.width,
                    height=garment.height,
                    state="available",
                    asset_ref_count=0,
                    created_at=now,
                )
            )
            await uow.assets.add(
                Asset(
                    id=person_id,
                    kind="person",
                    stored_object_id=person_object_id,
                    favorite=False,
                    content_state="available",
                    created_at=now,
                    updated_at=now,
                    person=PersonMetadata(asset_id=person_id),
                )
            )
            await uow.assets.add(
                Asset(
                    id=garment_id,
                    kind="garment",
                    stored_object_id=garment_object_id,
                    favorite=False,
                    content_state="available",
                    created_at=now,
                    updated_at=now,
                    garment=GarmentMetadata(
                        asset_id=garment_id, category="upper_body", source="photo"
                    ),
                )
            )
            await uow.provider_configs.add_config(
                ProviderConfig(
                    id=provider_id,
                    display_name="Counting",
                    provider_type="llm_image_edit",
                    state="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.provider_configs.add_revision(
                ProviderConfigRevision(
                    id=revision_id,
                    provider_id=provider_id,
                    revision=1,
                    adapter_type="counting_image_edit",
                    endpoint="https://fake.local",
                    model="counting",
                    timeout_seconds=30,
                    capabilities_json=ProviderCapabilities().to_json(),
                    vendor_parameters_json="{}",
                    created_at=now,
                )
            )
            await uow.jobs.add_job(
                Job(
                    id=job_id,
                    mode="precise_try_on",
                    state=state,  # type: ignore[arg-type]
                    candidate_count=1,
                    garment_asset_id=garment_id,
                    provider_id=provider_id,
                    provider_revision_id=revision_id,
                    provider_snapshot_json="{}",
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.jobs.add_item(
                JobItem(
                    id=item_id,
                    job_id=job_id,
                    person_asset_id=person_id,
                    candidate_index=0,
                    attempt=1,
                    state=state,  # type: ignore[arg-type]
                    block_reason=block_reason,  # type: ignore[arg-type]
                    external_execution_id=external_execution_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.commit()
        return {"job": job_id, "item": item_id}


async def _read(env: _Env, item_id: str) -> JobItem:
    async with SqlAlchemyUnitOfWork(env.runtime.sessions) as uow:
        item = await uow.jobs.get_item(item_id)
        assert item is not None
        return item


def test_storage_blocked_queued_work_resumes_without_failing(tmp_path: Path) -> None:
    env = _Env(tmp_path)
    execution = env.execution()
    scheduler = env.scheduler(execution)

    async def run() -> None:
        ids = await env.seed()
        env.state["blocked"] = True
        assert await scheduler.tick() == 0
        blocked = await _read(env, ids["item"])
        assert blocked.state == "queued"
        assert blocked.block_reason == "storage_capacity"
        assert env.adapter.submits == 0

        env.state["blocked"] = False
        assert await scheduler.tick() == 1
        done = await _read(env, ids["item"])
        assert done.state == "succeeded"
        assert env.adapter.submits == 1

    asyncio.run(run())
    env.close()


def test_remote_completion_is_not_resubmitted_while_storage_blocked(
    tmp_path: Path,
) -> None:
    env = _Env(tmp_path)
    execution = env.execution()
    scheduler = env.scheduler(execution)

    async def run() -> None:
        ids = await env.seed()
        env.state["block_after_submit"] = True
        assert await scheduler.tick() == 1
        paused = await _read(env, ids["item"])
        assert paused.state == "waiting_provider"
        assert paused.block_reason == "storage_capacity"
        assert paused.external_execution_id == f"ext-{ids['item']}"
        assert env.adapter.submits == 1
        assert env.adapter.fetches == 0

        env.state["blocked"] = False
        assert await scheduler.tick() == 1
        done = await _read(env, ids["item"])
        assert done.state == "succeeded"
        assert env.adapter.submits == 1
        assert env.adapter.fetches == 1

    asyncio.run(run())
    env.close()


def test_restart_requery_resolves_needs_attention_without_resubmit(tmp_path: Path) -> None:
    env = _Env(tmp_path)
    execution = env.execution()

    async def run() -> None:
        ids = await env.seed(
            state="needs_attention",
            block_reason="external_state_unknown",
            external_execution_id="ext-known",
        )
        reconciled = await execution.reconcile_external()
        assert reconciled == 1
        done = await _read(env, ids["item"])
        assert done.state == "succeeded"
        assert env.adapter.submits == 0
        assert env.adapter.fetches == 1

    asyncio.run(run())
    env.close()


def test_offline_node_waits_then_resumes_and_cancelled_never_runs(tmp_path: Path) -> None:
    env = _Env(tmp_path)
    execution = env.execution()
    scheduler = env.scheduler(execution)

    async def run() -> None:
        ids = await env.seed()
        env.state["availability"] = "temporarily_offline"
        await scheduler.tick()
        waiting = await _read(env, ids["item"])
        assert waiting.state == "waiting_provider"
        assert waiting.block_reason == "provider_offline"
        assert env.adapter.submits == 0

        env.state["availability"] = "available"
        await scheduler.tick()
        done = await _read(env, ids["item"])
        assert done.state == "succeeded"
        assert env.adapter.submits == 1

        cancelled = await env.seed(state="cancelled")
        assert await scheduler.tick() == 0
        still = await _read(env, cancelled["item"])
        assert still.state == "cancelled"

    asyncio.run(run())
    env.close()
