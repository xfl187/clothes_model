"""Deterministic fault and recovery coverage for the V1 release gate.

These tests never spend Provider credit and never require the network. They
assert on persisted state and injected transports rather than timing.
"""

import asyncio
import io
import itertools
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.storage import LocalFileStorage
from clothes_model.modules.assets.domain import Asset, GarmentMetadata, PersonMetadata, StoredObject
from clothes_model.modules.auth.application import TokenService
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
        self.database_url = f"sqlite+aiosqlite:///{(tmp_path / 'fault.db').as_posix()}"
        upgrade_database(self.database_url, tmp_path / "migration.lock")
        self.runtime = create_database_runtime(self.database_url, 5000)
        self.storage = LocalFileStorage(tmp_path / "storage")
        self.state: dict[str, object] = {"availability": "available", "query_state": "succeeded"}
        self.adapter = CountingAdapter(self.state)
        self.registry = ProviderRegistry([self.adapter], environment="test")
        self.provider_service = ProviderConfigService(
            lambda: SqlAlchemyUnitOfWork(self.runtime.sessions), self.registry, None
        )

    def execution(self) -> JobExecutionService:
        return JobExecutionService(
            lambda: SqlAlchemyUnitOfWork(self.runtime.sessions),
            self.provider_service,
            self.registry,
            self.storage,
            capacity=lambda: True,
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


def test_cancelled_item_is_never_reconciled_or_published(tmp_path: Path) -> None:
    env = _Env(tmp_path)
    execution = env.execution()

    async def run() -> None:
        ids = await env.seed(
            state="cancelled",
            external_execution_id="ext-late",
        )
        reconciled = await execution.reconcile_external()
        assert reconciled == 0
        item = await _read(env, ids["item"])
        assert item.state == "cancelled"
        assert env.adapter.fetches == 0
        assert env.adapter.submits == 0

    asyncio.run(run())
    env.close()


def test_running_external_success_is_published_without_resubmit(tmp_path: Path) -> None:
    env = _Env(tmp_path)
    execution = env.execution()

    async def run() -> None:
        ids = await env.seed(state="needs_attention", external_execution_id="ext-running")
        reconciled = await execution.reconcile_external()
        assert reconciled == 1
        item = await _read(env, ids["item"])
        assert item.state == "succeeded"
        assert env.adapter.submits == 0
        assert env.adapter.fetches == 1

    asyncio.run(run())
    env.close()


def test_unknown_external_state_never_resubmits(tmp_path: Path) -> None:
    env = _Env(tmp_path)
    execution = env.execution()

    async def run() -> None:
        env.state["query_state"] = "running"
        ids = await env.seed(state="needs_attention", external_execution_id="ext-unknown")
        reconciled = await execution.reconcile_external()
        assert reconciled == 1
        item = await _read(env, ids["item"])
        assert item.state == "running"
        assert env.adapter.submits == 0

    asyncio.run(run())
    env.close()


def _bootstrap(database_url: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            return {
                item.scope: item.value
                for item in await TokenService(
                    lambda: SqlAlchemyUnitOfWork(runtime.sessions)
                ).bootstrap()
            }
        finally:
            await runtime.close()

    return asyncio.run(run())


def _seed_assets_and_provider(database_url: str) -> dict[str, str]:
    person_id, garment_id = str(uuid4()), str(uuid4())
    provider_id, revision_id = str(uuid4()), str(uuid4())
    person_object, garment_object = str(uuid4()), str(uuid4())
    now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                for object_id, digest, path in (
                    (person_object, "b", "objects/bb/person"),
                    (garment_object, "c", "objects/cc/garment"),
                ):
                    await uow.stored_objects.add(
                        StoredObject(
                            id=object_id,
                            sha256=digest * 64,
                            relative_path=path,
                            content_type="image/jpeg",
                            size_bytes=128,
                            width=16,
                            height=8,
                            state="available",
                            asset_ref_count=0,
                            created_at=now,
                        )
                    )
                await uow.assets.add(
                    Asset(
                        id=person_id,
                        kind="person",
                        stored_object_id=person_object,
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
                        stored_object_id=garment_object,
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
                        display_name="Fake Provider",
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
                        adapter_type="fake_image_edit",
                        endpoint="https://fake.local",
                        model="fake-model",
                        timeout_seconds=30,
                        capabilities_json=ProviderCapabilities().to_json(),
                        vendor_parameters_json='{"scenario":"success"}',
                        created_at=now,
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"person": person_id, "garment": garment_id, "provider": provider_id}


def test_job_creation_blocked_when_storage_capacity_exhausted(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'capacity.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap(database_url)
    seeded = _seed_assets_and_provider(database_url)
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        storage_reserve_bytes=10**18,
    )
    body = {
        "person_asset_ids": [seeded["person"]],
        "garment_asset_id": seeded["garment"],
        "provider_id": seeded["provider"],
        "mode": "precise_try_on",
        "generation_options": {"candidate_count": 1},
    }
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/jobs",
            json=body,
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "capacity-job-0001",
            },
        )
        assert response.status_code == 507, response.text
        assert response.json()["code"] == "storage_capacity"
        assert response.json()["retryable"] is True
