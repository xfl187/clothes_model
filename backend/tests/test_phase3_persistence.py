import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from clothes_model.core.persistence import PersistenceConflict
from clothes_model.infrastructure.database import (
    SqlAlchemyUnitOfWork,
    create_database_runtime,
    models,
)
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.database.models import job_items, stored_objects
from clothes_model.modules.assets.domain import (
    Asset,
    GarmentMetadata,
    PersonMetadata,
    StoredObject,
)
from clothes_model.modules.jobs.domain import (
    GeneratedOutputRecord,
    Job,
    JobExecutionEvent,
    JobItem,
    JobPersonInput,
)
from clothes_model.modules.providers.domain import (
    ProviderConfig,
    ProviderConfigRevision,
    ProviderDefaultSelection,
)


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def now() -> datetime:
    return datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def stored_object(object_id: str, digest_character: str = "a") -> StoredObject:
    return StoredObject(
        id=object_id,
        sha256=digest_character * 64,
        relative_path=f"objects/{digest_character * 2}/{object_id}",
        content_type="image/jpeg",
        size_bytes=128,
        width=16,
        height=8,
        state="available",
        asset_ref_count=0,
        created_at=now(),
    )


def person_asset(asset_id: str, object_id: str) -> Asset:
    return Asset(
        id=asset_id,
        kind="person",
        stored_object_id=object_id,
        favorite=False,
        content_state="available",
        created_at=now(),
        updated_at=now(),
        person=PersonMetadata(asset_id=asset_id),
    )


def garment_asset(asset_id: str, object_id: str) -> Asset:
    return Asset(
        id=asset_id,
        kind="garment",
        stored_object_id=object_id,
        favorite=False,
        content_state="available",
        created_at=now(),
        updated_at=now(),
        garment=GarmentMetadata(asset_id=asset_id, category="upper_body", source="photo"),
    )


def output_asset(asset_id: str, object_id: str) -> Asset:
    return Asset(
        id=asset_id,
        kind="generated_output",
        stored_object_id=object_id,
        favorite=False,
        content_state="available",
        created_at=now(),
        updated_at=now(),
    )


def provider_config(provider_id: str = "provider-1") -> ProviderConfig:
    return ProviderConfig(
        id=provider_id,
        display_name="Image Edit Provider · model-a",
        provider_type="llm_image_edit",
        state="active",
        created_at=now(),
        updated_at=now(),
        secret_envelope='{"alg":"AES-256-GCM","ciphertext":"x","nonce":"y","v":1}',
        secret_updated_at=now(),
    )


def provider_revision(revision_id: str = "revision-1") -> ProviderConfigRevision:
    return ProviderConfigRevision(
        id=revision_id,
        provider_id="provider-1",
        revision=1,
        adapter_type="openai_image_edit",
        endpoint="https://provider.internal/v1",
        model="model-a",
        timeout_seconds=120,
        capabilities_json='{"schema_version":1}',
        vendor_parameters_json='{"temperature":0}',
        created_at=now(),
    )


def job(job_id: str = "job-1", *, state: str = "queued", candidate_count: int = 1) -> Job:
    return Job(
        id=job_id,
        mode="precise_try_on",
        state=state,  # type: ignore[arg-type]
        candidate_count=candidate_count,
        garment_asset_id="garment-asset",
        provider_id="provider-1",
        provider_revision_id="revision-1",
        provider_snapshot_json='{"label":"Image Edit Provider · model-a"}',
        advanced_parameters_json="{}",
        created_at=now(),
        updated_at=now(),
    )


def job_item(
    item_id: str = "item-1",
    *,
    state: str = "queued",
    attempt: int = 1,
    candidate_index: int = 0,
) -> JobItem:
    return JobItem(
        id=item_id,
        job_id="job-1",
        person_asset_id="person-asset",
        candidate_index=candidate_index,
        attempt=attempt,
        state=state,  # type: ignore[arg-type]
        created_at=now(),
        updated_at=now(),
    )


async def _seed_base(uow: SqlAlchemyUnitOfWork) -> None:
    await uow.stored_objects.add(stored_object("person-object", "b"))
    await uow.stored_objects.add(stored_object("garment-object", "c"))
    await uow.assets.add(person_asset("person-asset", "person-object"))
    await uow.assets.add(garment_asset("garment-asset", "garment-object"))
    await uow.provider_configs.add_config(provider_config())
    await uow.provider_configs.add_revision(provider_revision())
    await uow.provider_configs.set_default(
        ProviderDefaultSelection(
            id="default",
            provider_id="provider-1",
            config_revision_id="revision-1",
            updated_at=now(),
        )
    )
    await uow.commit()


def test_phase3_repositories_round_trip_and_rollback(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "jobs.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await _seed_base(uow)

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.stored_objects.add(stored_object("output-object", "d"))
                await uow.assets.add(output_asset("output-asset", "output-object"))
                await uow.jobs.add_job(job(candidate_count=2))
                await uow.jobs.add_person_input(
                    JobPersonInput(
                        job_id="job-1",
                        person_asset_id="person-asset",
                        ordinal=0,
                        created_at=now(),
                    )
                )
                await uow.jobs.add_item(job_item())
                await uow.jobs.add_item(
                    job_item("item-2", state="waiting_provider", candidate_index=1)
                )
                await uow.job_outputs.add_output(
                    GeneratedOutputRecord(
                        id="output-1",
                        job_item_id="item-1",
                        asset_id="output-asset",
                        favorite=False,
                        seed=42,
                        actual_parameters_json="{}",
                        quality_warnings_json="[]",
                        created_at=now(),
                    )
                )
                await uow.job_events.add_event(
                    JobExecutionEvent(
                        id="event-1",
                        job_id="job-1",
                        job_item_id="item-1",
                        event_type="item.state_changed",
                        from_state="queued",
                        to_state="running",
                        detail_json="{}",
                        occurred_at=now(),
                    )
                )
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                loaded_config = await uow.provider_configs.get_config("provider-1")
                current_revision = await uow.provider_configs.get_current_revision("provider-1")
                default = await uow.provider_configs.get_default()
                loaded_job = await uow.jobs.get_job("job-1")
                inputs = await uow.jobs.list_person_inputs("job-1")
                items = await uow.jobs.list_items("job-1")
                outputs = await uow.job_outputs.list_outputs("item-1")
                events = await uow.job_events.list_events("job-1")

                assert loaded_config is not None and loaded_config.secret_envelope is not None
                assert loaded_config.created_at.tzinfo is UTC
                assert current_revision is not None and current_revision.revision == 1
                assert default is not None and default.config_revision_id == "revision-1"
                assert loaded_job is not None and loaded_job.state == "queued"
                assert [entry.person_asset_id for entry in inputs] == ["person-asset"]
                assert [item.id for item in items] == ["item-1", "item-2"]
                assert len(outputs) == 1 and outputs[0].seed == 42
                assert len(events) == 1 and events[0].to_state == "running"

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.jobs.add_job(job("job-rolled-back"))
                # no commit: the Unit of Work must roll back on exit

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert await uow.jobs.get_job("job-rolled-back") is None
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_job_item_attempt_claim_and_output_invariants(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "constraints.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await _seed_base(uow)
                await uow.stored_objects.add(stored_object("output-object", "d"))
                await uow.assets.add(output_asset("output-asset", "output-object"))
                await uow.jobs.add_job(job())
                await uow.jobs.add_item(job_item())
                await uow.commit()

            # Only one non-terminal attempt may exist per candidate lineage.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(PersistenceConflict):
                    await uow.jobs.add_item(job_item("competing-active", attempt=2))
                await uow.rollback()

            # Duplicate (job, candidate, attempt) is rejected even for terminal attempts.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    update(job_items).where(job_items.c.id == "item-1").values(state="failed")
                )
                await uow.commit()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(PersistenceConflict):
                    await uow.jobs.add_item(job_item("duplicate-attempt", state="failed"))
                await uow.rollback()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.jobs.add_item(job_item("retry-attempt", attempt=2))
                await uow.session.execute(
                    update(job_items)
                    .where(job_items.c.id == "item-1")
                    .values(superseded_by_job_item_id="retry-attempt")
                )
                await uow.commit()

            # Claim state is all-or-nothing and leases must move forward.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        update(job_items)
                        .where(job_items.c.id == "item-1")
                        .values(claimant_token="orphan-claim")
                    )
                await uow.rollback()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        update(job_items)
                        .where(job_items.c.id == "item-1")
                        .values(
                            claimant_token="token",
                            claimed_at=now(),
                            lease_expires_at=now(),
                        )
                    )
                await uow.rollback()

            # External execution identity is unique where present.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    update(job_items)
                    .where(job_items.c.id == "item-1")
                    .values(external_execution_id="execution-1")
                )
                await uow.session.execute(
                    update(job_items)
                    .where(job_items.c.id == "retry-attempt")
                    .values(external_execution_id="execution-2")
                )
                await uow.commit()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        update(job_items)
                        .where(job_items.c.id == "retry-attempt")
                        .values(external_execution_id="execution-1")
                    )
                await uow.rollback()

            # Generated-output assets participate in content-addressed reference counts.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                ref_count = await uow.session.scalar(
                    select(stored_objects.c.asset_ref_count).where(
                        stored_objects.c.id == "output-object"
                    )
                )
                assert ref_count == 1
                await uow.job_outputs.add_output(
                    GeneratedOutputRecord(
                        id="output-1",
                        job_item_id="retry-attempt",
                        asset_id="output-asset",
                        favorite=False,
                        created_at=now(),
                    )
                )
                await uow.commit()

            # Job input assets stay protected while the job exists.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        delete(models.assets).where(models.assets.c.id == "garment-asset")
                    )
                await uow.rollback()
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_atomic_claim_has_single_winner(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "claim.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        ready = asyncio.Event()
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await _seed_base(uow)
                await uow.jobs.add_job(job())
                await uow.jobs.add_item(job_item())
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                claimable = await uow.jobs.list_claimable_item_ids(
                    now=now(), states=("queued", "waiting_provider"), limit=5
                )
                assert claimable == ["item-1"]

            async def contender(claimant: str) -> bool:
                await ready.wait()
                async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                    claimed = await uow.jobs.claim_item(
                        "item-1",
                        claimant_token=claimant,
                        claimed_at=now(),
                        lease_expires_at=now() + timedelta(minutes=5),
                    )
                    await uow.commit()
                    return claimed

            tasks = [
                asyncio.create_task(contender("scheduler-a")),
                asyncio.create_task(contender("scheduler-b")),
            ]
            ready.set()
            results = await asyncio.gather(*tasks)
            assert sorted(results) == [False, True]

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert (
                    await uow.jobs.list_claimable_item_ids(
                        now=now(), states=("queued", "waiting_provider")
                    )
                    == []
                )
                await uow.jobs.release_claim("item-1")
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert await uow.jobs.list_claimable_item_ids(
                    now=now(), states=("queued", "waiting_provider")
                ) == ["item-1"]

            # Compare-and-set rejects a competing transition.
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                changed = await uow.session.execute(
                    update(job_items)
                    .where(job_items.c.id == "item-1", job_items.c.state == "queued")
                    .values(state="preparing")
                )
                assert changed.rowcount == 1
                await uow.commit()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert not await uow.jobs.compare_and_set_item_state(
                    "item-1", ("queued",), "preparing"
                )
                assert await uow.jobs.compare_and_set_item_state(
                    "item-1", ("preparing",), "running", {"updated_at": now()}
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_generated_output_asset_matches_kind_contract(tmp_path: Path) -> None:
    database_url = sqlite_url(tmp_path / "output-kind.db")
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.stored_objects.add(stored_object("output-object", "e"))
                await uow.assets.add(output_asset("output-asset", "output-object"))
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(PersistenceConflict):
                    await uow.assets.add(
                        Asset(
                            id="bad-output",
                            kind="generated_output",
                            stored_object_id="output-object",
                            favorite=False,
                            content_state="available",
                            created_at=now(),
                            updated_at=now(),
                            person=PersonMetadata(asset_id="bad-output"),
                        )
                    )
                await uow.rollback()
        finally:
            await runtime.close()

    asyncio.run(exercise())
