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
from clothes_model.modules.assets.domain import (
    Asset,
    AssetReference,
    GarmentMetadata,
    PersonMetadata,
    StoredObject,
)
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.jobs.domain import GeneratedOutputRecord, Job, JobItem, JobPersonInput
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
)


def _now() -> datetime:
    return datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


_counter = itertools.count(1)


def _png() -> bytes:
    value = next(_counter)
    buffer = io.BytesIO()
    Image.new("RGB", (16, 12), (value % 256, (value * 3) % 256, (value * 7) % 256)).save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


def _bootstrap(database_url: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
            return {item.scope: item.value for item in await service.bootstrap()}
        finally:
            await runtime.close()

    return asyncio.run(run())


def _seed(database_url: str, storage_root: Path) -> dict[str, object]:
    now = _now()
    storage = LocalFileStorage(storage_root)
    provider_id, revision_id = str(uuid4()), str(uuid4())
    active_job, active_item = str(uuid4()), str(uuid4())
    done_job, done_item, output_record = str(uuid4()), str(uuid4()), str(uuid4())
    ids = {
        "person_active": str(uuid4()),
        "garment_active": str(uuid4()),
        "person_done": str(uuid4()),
        "garment_done": str(uuid4()),
        "output": str(uuid4()),
        "provider": provider_id,
        "active_job": active_job,
        "done_job": done_job,
    }
    relative_paths: list[str] = []
    snapshot = (
        '{"label":"Fake Provider","adapter_type":"fake_image_edit","model":"fake-model",'
        '"capabilities_schema_version":1,"capabilities":{}}'
    )

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                async def add_asset(asset_id: str, kind: str) -> None:
                    normalized = storage.normalize_and_store(_png())
                    relative_paths.append(normalized.relative_path)
                    object_id = str(uuid4())
                    await uow.stored_objects.add(
                        StoredObject(
                            id=object_id,
                            sha256=normalized.sha256,
                            relative_path=normalized.relative_path,
                            content_type=normalized.content_type,
                            size_bytes=normalized.size_bytes,
                            width=normalized.width,
                            height=normalized.height,
                            state="available",
                            asset_ref_count=0,
                            created_at=now,
                        )
                    )
                    person = PersonMetadata(asset_id=asset_id) if kind == "person" else None
                    garment = (
                        GarmentMetadata(asset_id=asset_id, category="upper_body", source="photo")
                        if kind == "garment"
                        else None
                    )
                    await uow.assets.add(
                        Asset(
                            id=asset_id,
                            kind=kind,  # type: ignore[arg-type]
                            stored_object_id=object_id,
                            favorite=False,
                            content_state="available",
                            created_at=now,
                            updated_at=now,
                            person=person,
                            garment=garment,
                        )
                    )

                for key, kind in (
                    ("person_active", "person"),
                    ("garment_active", "garment"),
                    ("person_done", "person"),
                    ("garment_done", "garment"),
                    ("output", "generated_output"),
                ):
                    await add_asset(str(ids[key]), kind)

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
                        capabilities_json=ProviderCapabilities(
                            manual_mask=True, region_mask=True
                        ).to_json(),
                        vendor_parameters_json='{"scenario":"success"}',
                        created_at=now,
                    )
                )

                await uow.jobs.add_job(
                    Job(
                        id=active_job,
                        mode="precise_try_on",
                        state="queued",
                        candidate_count=1,
                        garment_asset_id=str(ids["garment_active"]),
                        provider_id=provider_id,
                        provider_revision_id=revision_id,
                        provider_snapshot_json=snapshot,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.jobs.add_person_input(
                    JobPersonInput(
                        job_id=active_job,
                        person_asset_id=str(ids["person_active"]),
                        ordinal=0,
                        created_at=now,
                    )
                )
                await uow.jobs.add_item(
                    JobItem(
                        id=active_item,
                        job_id=active_job,
                        person_asset_id=str(ids["person_active"]),
                        candidate_index=0,
                        attempt=1,
                        state="queued",
                        created_at=now,
                        updated_at=now,
                    )
                )
                for asset_key in ("garment_active", "person_active"):
                    await uow.asset_references.add(
                        AssetReference(
                            id=str(uuid4()),
                            asset_id=str(ids[asset_key]),
                            source_kind="job",
                            source_id=active_job,
                            active=True,
                            created_at=now,
                            display_label="试穿任务",
                        )
                    )

                await uow.jobs.add_job(
                    Job(
                        id=done_job,
                        mode="precise_try_on",
                        state="succeeded",
                        candidate_count=1,
                        garment_asset_id=str(ids["garment_done"]),
                        provider_id=provider_id,
                        provider_revision_id=revision_id,
                        provider_snapshot_json=snapshot,
                        mask_asset_id=str(uuid4()),
                        related_job_id=active_job,
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.jobs.add_person_input(
                    JobPersonInput(
                        job_id=done_job,
                        person_asset_id=str(ids["person_done"]),
                        ordinal=0,
                        created_at=now,
                    )
                )
                await uow.jobs.add_item(
                    JobItem(
                        id=done_item,
                        job_id=done_job,
                        person_asset_id=str(ids["person_done"]),
                        candidate_index=0,
                        attempt=1,
                        state="succeeded",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.job_outputs.add_output(
                    GeneratedOutputRecord(
                        id=output_record,
                        job_item_id=done_item,
                        asset_id=str(ids["output"]),
                        favorite=False,
                        created_at=now,
                        seed=7,
                    )
                )
                await uow.asset_references.add(
                    AssetReference(
                        id=str(uuid4()),
                        asset_id=str(ids["output"]),
                        source_kind="generated_output",
                        source_id=done_item,
                        active=True,
                        created_at=now,
                        display_label="生成结果",
                    )
                )
                for asset_key in ("garment_done", "person_done"):
                    await uow.asset_references.add(
                        AssetReference(
                            id=str(uuid4()),
                            asset_id=str(ids[asset_key]),
                            source_kind="job",
                            source_id=done_job,
                            active=True,
                            created_at=now,
                            display_label="试穿任务",
                        )
                    )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"ids": ids, "relative_paths": relative_paths, "done_item": done_item}


def _client(database_url: str, tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
    )
    return TestClient(create_app(settings))


def _prepare(tmp_path: Path) -> tuple[str, dict[str, str], dict[str, object]]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'lifecycle.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap(database_url)
    return database_url, tokens, _seed(database_url, tmp_path / "storage")


def test_generated_output_favorite_reconciles_with_asset(tmp_path: Path) -> None:
    database_url, tokens, seeded = _prepare(tmp_path)
    ids = seeded["ids"]
    assert isinstance(ids, dict)
    headers = {"Authorization": f"Bearer {tokens['app']}"}

    with _client(database_url, tmp_path) as client:
        job = client.get(f"/api/v1/jobs/{ids['done_job']}", headers=headers).json()
        assert job["items"][0]["outputs"][0]["favorite"] is False

        patched = client.patch(
            f"/api/v1/assets/{ids['output']}", headers=headers, json={"favorite": True}
        )
        assert patched.status_code == 200 and patched.json()["favorite"] is True

        refreshed = client.get(f"/api/v1/jobs/{ids['done_job']}", headers=headers).json()
        assert refreshed["items"][0]["outputs"][0]["favorite"] is True


def test_content_deletion_blocks_active_and_allows_terminal_references(tmp_path: Path) -> None:
    database_url, tokens, seeded = _prepare(tmp_path)
    ids = seeded["ids"]
    assert isinstance(ids, dict)
    headers = {"Authorization": f"Bearer {tokens['app']}"}

    with _client(database_url, tmp_path) as client:
        active_references = client.get(
            f"/api/v1/assets/{ids['person_active']}/references", headers=headers
        ).json()
        assert [item["source_kind"] for item in active_references["items"]] == ["job"]
        assert active_references["items"][0]["source_id"] == ids["active_job"]

        blocked = client.delete(
            f"/api/v1/assets/{ids['person_active']}/content", headers=headers
        )
        assert blocked.status_code == 409
        problem = blocked.json()
        assert problem["code"] == "asset_referenced"
        assert problem["context"]["reference_count"] == 1

        assert (
            client.get(
                f"/api/v1/assets/{ids['person_done']}/references", headers=headers
            ).json()["items"]
            == []
        )
        deleted = client.delete(f"/api/v1/assets/{ids['person_done']}/content", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["outcome"] == "content_deleted"
        assert deleted.json()["asset"]["lifecycle"] == "deleted_content"
        assert deleted.json()["asset"]["content_available"] is False

        assert (
            client.get(
                f"/api/v1/assets/{ids['output']}/references", headers=headers
            ).json()["items"]
            == []
        )
        output_deleted = client.delete(f"/api/v1/assets/{ids['output']}/content", headers=headers)
        assert output_deleted.status_code == 200
        assert output_deleted.json()["asset"]["lifecycle"] == "deleted_content"


def test_related_job_lineage_is_rendered_without_internal_paths(tmp_path: Path) -> None:
    database_url, tokens, seeded = _prepare(tmp_path)
    ids = seeded["ids"]
    assert isinstance(ids, dict)
    relative_paths = seeded["relative_paths"]
    assert isinstance(relative_paths, list)
    headers = {"Authorization": f"Bearer {tokens['app']}"}

    with _client(database_url, tmp_path) as client:
        response = client.get(f"/api/v1/jobs/{ids['done_job']}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["related_job_id"] == ids["active_job"]
        assert body["mask_asset_id"]
        assert "relative_path" not in response.text
        assert "fake.local" not in response.text
        for relative in relative_paths:
            assert relative not in response.text
