import asyncio
import io
import itertools
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select, update

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database import models as db
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.scheduler import JobScheduler, reconcile_claims
from clothes_model.infrastructure.storage import LocalFileStorage
from clothes_model.modules.assets.domain import Asset, GarmentMetadata, PersonMetadata, StoredObject
from clothes_model.modules.jobs.domain import Job, JobItem
from clothes_model.modules.jobs.infrastructure.execution import JobExecutionService
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
)
from clothes_model.modules.providers.infrastructure import FakeImageEditAdapter, ProviderRegistry

_counter = itertools.count(1)


def _png() -> bytes:
    value = next(_counter)
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), (value % 256, (value * 7) % 256, (value * 13) % 256)).save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


def _services(database_url: str, root: Path, clock=None):
    runtime = create_database_runtime(database_url, 5000)
    storage = LocalFileStorage(root)
    registry = ProviderRegistry([FakeImageEditAdapter()], environment="test")
    provider_service = ProviderConfigService(
        lambda: SqlAlchemyUnitOfWork(runtime.sessions), registry, None
    )
    execution = JobExecutionService(
        lambda: SqlAlchemyUnitOfWork(runtime.sessions),
        provider_service,
        registry,
        storage,
        clock=clock,
    )
    return runtime, storage, registry, provider_service, execution


async def _seed_job(runtime, storage, scenario: str, *, state: str = "queued") -> dict[str, str]:
    person = storage.normalize_and_store(_png())
    garment = storage.normalize_and_store(_png())
    provider_id, revision_id = str(uuid4()), str(uuid4())
    person_id, garment_id, job_id, item_id = (str(uuid4()) for _ in range(4))
    person_object_id, garment_object_id = str(uuid4()), str(uuid4())
    now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
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
                garment=GarmentMetadata(asset_id=garment_id, category="upper_body", source="photo"),
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
                vendor_parameters_json='{"scenario":"' + scenario + '"}',
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
                created_at=now,
                updated_at=now,
            )
        )
        await uow.commit()
    return {
        "provider": provider_id,
        "revision": revision_id,
        "person": person_id,
        "garment": garment_id,
        "job": job_id,
        "item": item_id,
    }


def test_scheduler_executes_item_and_persists_private_output(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'exec.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    runtime, storage, _, _, execution = _services(database_url, tmp_path / "storage")

    async def run() -> None:
        try:
            ids = await _seed_job(runtime, storage, "success")
            scheduler = JobScheduler(runtime.sessions, execution)
            assert await scheduler.tick() == 1

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                item = await uow.jobs.get_item(ids["item"])
                job = await uow.jobs.get_job(ids["job"])
                outputs = await uow.job_outputs.list_outputs(ids["item"])
                generated = await uow.session.scalar(
                    select(func.count()).select_from(db.assets).where(
                        db.assets.c.kind == "generated_output"
                    )
                )
                references = await uow.session.scalar(
                    select(func.count()).select_from(db.asset_references).where(
                        db.asset_references.c.source_kind == "generated_output"
                    )
                )
                assert item is not None and item.state == "succeeded"
                assert item.claimant_token is None
                assert job is not None and job.state == "succeeded"
                assert len(outputs) == 1
                assert generated == 1 and references == 1
                output_asset = await uow.session.scalar(
                    select(db.assets.c.stored_object_id).where(
                        db.assets.c.kind == "generated_output"
                    )
                )
                relative = await uow.session.scalar(
                    select(db.stored_objects.c.relative_path).where(
                        db.stored_objects.c.id == output_asset
                    )
                )
                assert relative is not None and (storage.root / relative).is_file()
        finally:
            await runtime.close()

    asyncio.run(run())


def test_offline_scenario_waits_without_consuming_retry(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'offline.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    runtime, storage, _, _, execution = _services(database_url, tmp_path / "storage")

    async def run() -> None:
        try:
            ids = await _seed_job(runtime, storage, "offline")
            scheduler = JobScheduler(runtime.sessions, execution)
            await scheduler.tick()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                item = await uow.jobs.get_item(ids["item"])
                job = await uow.jobs.get_job(ids["job"])
                assert item is not None and item.state == "waiting_provider"
                assert item.block_reason == "provider_offline"
                assert job is not None and job.state == "waiting_provider"
        finally:
            await runtime.close()

    asyncio.run(run())


def test_transient_scenario_backs_off_then_succeeds(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'transient.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    state = {"now": datetime(2026, 9, 27, 12, 0, tzinfo=UTC)}
    clock = lambda: state["now"]  # noqa: E731 - tiny test clock
    runtime, storage, _, _, execution = _services(database_url, tmp_path / "storage", clock)

    async def run() -> None:
        try:
            ids = await _seed_job(runtime, storage, "transient")
            scheduler = JobScheduler(runtime.sessions, execution, clock=clock)
            await scheduler.tick()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                item = await uow.jobs.get_item(ids["item"])
                assert item is not None and item.state == "queued"
                assert item.block_reason == "retry_backoff"
                assert item.transient_attempts == 1
                assert item.next_attempt_at is not None
                # Backoff is respected: the item is not immediately claimable.
                claimable = await uow.jobs.list_claimable_item_ids(
                    now=state["now"], states=("queued", "waiting_provider")
                )
                assert ids["item"] not in claimable

            # After the backoff window the second query succeeds.
            state["now"] = state["now"] + timedelta(minutes=1)
            await scheduler.tick()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                item = await uow.jobs.get_item(ids["item"])
                assert item is not None and item.state == "succeeded"
        finally:
            await runtime.close()

    asyncio.run(run())


def test_ambiguous_enters_needs_attention_and_reconcile(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'ambiguous.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    runtime, storage, _, _, execution = _services(database_url, tmp_path / "storage")

    async def run() -> None:
        try:
            ids = await _seed_job(runtime, storage, "ambiguous")
            scheduler = JobScheduler(runtime.sessions, execution)
            await scheduler.tick()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                item = await uow.jobs.get_item(ids["item"])
                assert item is not None and item.state == "needs_attention"

            # Reconcile: a crashed running lease becomes needs_attention; preparing restarts.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
                await uow.session.execute(
                    update(db.job_items)
                    .where(db.job_items.c.id == ids["item"])
                    .values(
                        state="running",
                        claimant_token="crashed",
                        claimed_at=now - timedelta(minutes=10),
                        lease_expires_at=now - timedelta(minutes=5),
                    )
                )
                await uow.commit()
            await reconcile_claims(runtime.sessions, datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                item = await uow.jobs.get_item(ids["item"])
                assert item is not None and item.state == "needs_attention"
                assert item.block_reason == "external_state_unknown"
        finally:
            await runtime.close()

    asyncio.run(run())
