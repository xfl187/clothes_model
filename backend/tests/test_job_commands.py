import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.assets.domain import Asset, GarmentMetadata, PersonMetadata, StoredObject
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
)


def _now() -> datetime:
    return datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _bootstrap(database_url: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
            return {item.scope: item.value for item in await service.bootstrap()}
        finally:
            await runtime.close()

    return asyncio.run(run())


def _seed(database_url: str, candidates: int) -> dict[str, object]:
    person_id, garment_id = str(uuid4()), str(uuid4())
    provider_id, revision_id = str(uuid4()), str(uuid4())
    person_object, garment_object = str(uuid4()), str(uuid4())

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
                            created_at=_now(),
                        )
                    )
                await uow.assets.add(
                    Asset(
                        id=person_id,
                        kind="person",
                        stored_object_id=person_object,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
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
                        created_at=_now(),
                        updated_at=_now(),
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
                        created_at=_now(),
                        updated_at=_now(),
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
                        created_at=_now(),
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"person": person_id, "garment": garment_id, "provider": provider_id}


def _client(database_url: str, tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
    )
    return TestClient(create_app(settings))


def _create_job(client: TestClient, app_token: str, seeded: dict[str, object], candidates: int):
    response = client.post(
        "/api/v1/jobs",
        json={
            "person_asset_ids": [seeded["person"]],
            "garment_asset_id": seeded["garment"],
            "provider_id": seeded["provider"],
            "mode": "precise_try_on",
            "generation_options": {"candidate_count": candidates},
        },
        headers={
            "Authorization": f"Bearer {app_token}",
            "Idempotency-Key": f"create-{uuid4()}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _set_state(
    database_path: Path, item_id: str, state: str, external_id: str | None = None
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE job_items SET state = ?, external_execution_id = ? WHERE id = ?",
            (state, external_id, item_id),
        )
        connection.commit()


def test_cancel_whole_job_and_single_candidate(tmp_path: Path) -> None:
    database_path = tmp_path / "cancel.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap(database_url)
    seeded = _seed(database_url, 1)
    auth = {"Authorization": f"Bearer {tokens['app']}", "Idempotency-Key": "cancel-key-0001"}

    with _client(database_url, tmp_path) as client:
        job = _create_job(client, tokens["app"], seeded, 2)
        item_id = job["items"][0]["id"]

        one = client.post(f"/api/v1/job-items/{item_id}/cancel", headers=auth)
        assert one.status_code == 200
        states = {item["id"]: item["state"] for item in one.json()["job"]["items"]}
        assert states[item_id] == "cancelled"
        assert sorted(states.values()) == ["cancelled", "queued"]

        whole = client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=auth)
        assert whole.status_code == 200
        assert whole.json()["job"]["state"] == "cancelled"
        assert all(item["state"] == "cancelled" for item in whole.json()["job"]["items"])


def test_retry_creates_traceable_new_attempt(tmp_path: Path) -> None:
    database_path = tmp_path / "retry.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap(database_url)
    seeded = _seed(database_url, 1)
    auth = {"Authorization": f"Bearer {tokens['app']}", "Idempotency-Key": "retry-key-0001"}

    with _client(database_url, tmp_path) as client:
        job = _create_job(client, tokens["app"], seeded, 1)
        item_id = job["items"][0]["id"]
        _set_state(database_path, item_id, "failed")

        retried = client.post(f"/api/v1/job-items/{item_id}/retry", headers=auth)
        assert retried.status_code == 201, retried.text
        body = retried.json()
        new_id = body["created_job_item_id"]
        items = {item["id"]: item for item in body["job"]["items"]}
        assert items[new_id]["attempt"] == 2
        assert items[new_id]["retry_of_job_item_id"] == item_id
        assert items[item_id]["superseded_by_job_item_id"] == new_id

        conflict = client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=auth)
        assert conflict.status_code == 200


def test_admin_diagnostics_are_redacted(tmp_path: Path) -> None:
    database_path = tmp_path / "diagnostics.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap(database_url)
    seeded = _seed(database_url, 1)

    with _client(database_url, tmp_path) as client:
        job = _create_job(client, tokens["app"], seeded, 1)
        login = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": tokens["admin"]}
        )
        assert login.status_code == 201

        listing = client.get("/api/v1/admin/diagnostics/jobs")
        assert listing.status_code == 200
        item = listing.json()["items"][0]
        assert item["job_id"] == job["id"]
        assert item["provider_label"]

        detail = client.get(f"/api/v1/admin/diagnostics/jobs/{job['id']}")
        assert detail.status_code == 200
        serialized = detail.text
        assert tokens["admin"] not in serialized
        assert job["provider_snapshot"]["semantic_parameters"] is not None
        assert "redacted_external_events" in detail.json()


def test_requery_and_finish_failed_on_needs_attention(tmp_path: Path) -> None:
    database_path = tmp_path / "requery.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap(database_url)
    seeded = _seed(database_url, 1)
    auth = {"Authorization": f"Bearer {tokens['app']}", "Idempotency-Key": "requery-key-0001"}

    with _client(database_url, tmp_path) as client:
        job = _create_job(client, tokens["app"], seeded, 1)
        item_id = job["items"][0]["id"]
        _set_state(database_path, item_id, "needs_attention", external_id="fake-external")

        # Requery of an untracked external execution stays ambiguous and never resubmits.
        requery = client.post(f"/api/v1/job-items/{item_id}/requery", headers=auth)
        assert requery.status_code == 200
        assert requery.json()["job"]["items"][0]["state"] == "needs_attention"

        finished = client.post(
            f"/api/v1/job-items/{item_id}/finish-failed",
            json={"reason": "operator confirmed failure"},
            headers=auth,
        )
        assert finished.status_code == 200
        assert finished.json()["job"]["items"][0]["state"] == "failed"
        assert finished.json()["job"]["state"] == "failed"
