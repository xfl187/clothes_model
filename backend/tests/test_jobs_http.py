import asyncio
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
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
)


def _now() -> datetime:
    return datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _bootstrap_tokens(database_url: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
            return {item.scope: item.value for item in await service.bootstrap()}
        finally:
            await runtime.close()

    return asyncio.run(run())


def _seed(
    database_url: str,
    provider_id: str,
    scenario: str,
    state: str,
    *,
    manual_mask: bool = True,
) -> dict[str, str]:
    person_id, garment_id, mask_id = str(uuid4()), str(uuid4()), str(uuid4())
    person_object_id, garment_object_id, mask_object_id = (
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
    )
    provider_revision_id = str(uuid4())

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.stored_objects.add(
                    StoredObject(
                        id=person_object_id,
                        sha256="b" * 64,
                        relative_path="objects/bb/person",
                        content_type="image/jpeg",
                        size_bytes=128,
                        width=16,
                        height=8,
                        state="available",
                        asset_ref_count=0,
                        created_at=_now(),
                    )
                )
                await uow.stored_objects.add(
                    StoredObject(
                        id=mask_object_id,
                        sha256="d" * 64,
                        relative_path="objects/dd/mask",
                        content_type="image/png",
                        size_bytes=64,
                        width=16,
                        height=8,
                        state="available",
                        asset_ref_count=0,
                        created_at=_now(),
                    )
                )
                await uow.stored_objects.add(
                    StoredObject(
                        id=garment_object_id,
                        sha256="c" * 64,
                        relative_path="objects/cc/garment",
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
                        stored_object_id=person_object_id,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                        person=PersonMetadata(asset_id=person_id),
                    )
                )
                await uow.assets.add(
                    Asset(
                        id=mask_id,
                        kind="mask",
                        stored_object_id=mask_object_id,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )
                await uow.assets.add(
                    Asset(
                        id=garment_id,
                        kind="garment",
                        stored_object_id=garment_object_id,
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
                        state=state,  # type: ignore[arg-type]
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )
                await uow.provider_configs.add_revision(
                    ProviderConfigRevision(
                        id=provider_revision_id,
                        provider_id=provider_id,
                        revision=1,
                        adapter_type="fake_image_edit",
                        endpoint="https://fake.local",
                        model="fake-model",
                        timeout_seconds=30,
                        capabilities_json=ProviderCapabilities(
                            manual_mask=manual_mask, region_mask=manual_mask
                        ).to_json(),
                        vendor_parameters_json='{"scenario":"' + scenario + '"}',
                        created_at=_now(),
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"person": person_id, "garment": garment_id, "mask": mask_id}


def _job_body(seeded: dict[str, str], provider_id: str, candidates: int = 2) -> dict[str, object]:
    return {
        "person_asset_ids": [seeded["person"]],
        "garment_asset_id": seeded["garment"],
        "provider_id": provider_id,
        "mode": "precise_try_on",
        "generation_options": {"candidate_count": candidates},
    }


def _client(database_url: str, tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
    )
    return TestClient(create_app(settings))


def test_archived_provider_preserves_history_and_blocks_new_work(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'archived-provider.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap_tokens(database_url)
    provider_id = str(uuid4())
    seeded = _seed(database_url, provider_id, "success", "active")
    app_headers = {
        "Authorization": f"Bearer {tokens['app']}",
        "Idempotency-Key": "archive-history-job-0001",
    }

    with _client(database_url, tmp_path) as client:
        created = client.post(
            "/api/v1/jobs", json=_job_body(seeded, provider_id, 1), headers=app_headers
        )
        assert created.status_code == 201, created.text
        job = created.json()
        revision_id = job["provider_config_ref"]["config_version_id"]

        login = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": tokens["admin"]}
        )
        assert login.status_code == 201
        csrf = login.json()["csrf_token"]
        archive_headers = {
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "archive-history-provider-0001",
        }

        archived = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/archive",
            headers=archive_headers,
        )
        assert archived.status_code == 200, archived.text
        assert archived.json()["state"] == "disabled"
        repeated = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/archive",
            headers={**archive_headers, "Idempotency-Key": "archive-history-provider-0002"},
        )
        assert repeated.status_code == 200
        assert repeated.json()["state"] == "disabled"

        admin_items = client.get("/api/v1/admin/provider-configs").json()["items"]
        assert any(
            item["id"] == provider_id and item["state"] == "disabled"
            for item in admin_items
        )
        app_items = client.get(
            "/api/v1/providers", headers={"Authorization": f"Bearer {tokens['app']}"}
        ).json()["items"]
        assert all(item["id"] != provider_id for item in app_items)

        blocked = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded, provider_id, 1),
            headers={**app_headers, "Idempotency-Key": "archive-history-job-0002"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "provider_not_usable"
        assert (
            client.get(
                f"/api/v1/jobs/{job['id']}",
                headers={"Authorization": f"Bearer {tokens['app']}"},
            ).status_code
            == 200
        )

        service = ProviderConfigService(
            lambda: SqlAlchemyUnitOfWork(client.app.state.database.sessions),
            client.app.state.provider_registry,
            client.app.state.secret_cipher,
        )
        _, locked_config, locked_revision = asyncio.run(
            service.resolve_invocation(provider_id, revision_id)
        )
        assert locked_config.state == "disabled"
        assert locked_revision.id == revision_id

        archived_update = client.patch(
            f"/api/v1/admin/provider-configs/{provider_id}",
            json={
                "display_name": "Archived Provider",
                "type": "llm_image_edit",
                "adapter_type": "fake_image_edit",
                "endpoint": "https://fake.local",
                "model": "fake-model",
                "timeout_seconds": 30,
                "vendor_parameters": {"scenario": "success"},
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert archived_update.status_code == 409
        assert archived_update.json()["code"] == "provider_archived"
        for action in ("validate", "enable"):
            response = client.post(
                f"/api/v1/admin/provider-configs/{provider_id}/{action}",
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": f"archived-{action}-0001",
                },
            )
            assert response.status_code == 409
            assert response.json()["code"] == "provider_archived"
        archived_default = client.put(
            "/api/v1/admin/configuration/default-provider",
            json={"provider_id": provider_id, "confirm_new_jobs_only": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert archived_default.status_code == 409
        assert archived_default.json()["code"] == "provider_archived"

        referenced_delete = client.delete(
            f"/api/v1/admin/provider-configs/{provider_id}",
            headers={"X-CSRF-Token": csrf},
        )
        assert referenced_delete.status_code == 409
        assert referenced_delete.json()["code"] == "provider_has_job_history"

        restored = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/restore",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "restore-history-provider-0001",
            },
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["state"] == "inactive"
        repeated_restore = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/restore",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "restore-history-provider-0002",
            },
        )
        assert repeated_restore.status_code == 409
        assert repeated_restore.json()["code"] == "provider_not_archived"


def test_job_creation_idempotency_queries_and_validation(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'jobs.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap_tokens(database_url)
    provider_id = str(uuid4())
    seeded = _seed(database_url, provider_id, "success", "active")
    headers = {"Authorization": f"Bearer {tokens['app']}", "Idempotency-Key": "job-create-key-0001"}

    with _client(database_url, tmp_path) as client:
        created = client.post("/api/v1/jobs", json=_job_body(seeded, provider_id), headers=headers)
        assert created.status_code == 201, created.text
        job = created.json()
        assert job["state"] == "queued"
        assert len(job["items"]) == 2
        assert job["provider_config_ref"]["revision"] == 1
        assert job["provider_snapshot"]["adapter_type"] == "fake_image_edit"
        assert job["provider_snapshot"]["capabilities"]["manual_mask"]["supported"] is True
        job_id = job["id"]

        correction = client.post(
            "/api/v1/jobs",
            json={
                **_job_body(seeded, provider_id, candidates=1),
                "mask_asset_id": seeded["mask"],
                "related_job_id": job_id,
            },
            headers={**headers, "Idempotency-Key": "job-mask-correction-0001"},
        )
        assert correction.status_code == 201, correction.text
        assert correction.json()["mask_asset_id"] == seeded["mask"]
        assert correction.json()["related_job_id"] == job_id

        wrong_mask_kind = client.post(
            "/api/v1/jobs",
            json={
                **_job_body(seeded, provider_id, candidates=1),
                "mask_asset_id": seeded["person"],
                "related_job_id": job_id,
            },
            headers={**headers, "Idempotency-Key": "job-mask-wrong-kind-0001"},
        )
        assert wrong_mask_kind.status_code == 422

        replay = client.post("/api/v1/jobs", json=_job_body(seeded, provider_id), headers=headers)
        assert replay.status_code == 201 and replay.json()["id"] == job_id

        conflict = client.post(
            "/api/v1/jobs", json=_job_body(seeded, provider_id, candidates=1), headers=headers
        )
        assert conflict.status_code == 409

        fetched = client.get(
            f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {tokens['app']}"}
        )
        assert fetched.status_code == 200 and fetched.json()["id"] == job_id

        page = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {tokens['app']}"})
        assert page.status_code == 200 and page.json()["has_more"] is False
        assert {item["id"] for item in page.json()["items"]} == {
            job_id,
            correction.json()["id"],
        }

        item_id = job["items"][0]["id"]
        item = client.get(
            f"/api/v1/job-items/{item_id}", headers={"Authorization": f"Bearer {tokens['app']}"}
        )
        assert item.status_code == 200 and item.json()["job_id"] == job_id

        missing = client.post(
            "/api/v1/jobs",
            json={
                **_job_body(seeded, provider_id),
                "garment_asset_id": str(uuid4()),
            },
            headers={**headers, "Idempotency-Key": "job-create-key-0002"},
        )
        assert missing.status_code == 422

        unusable = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded, str(uuid4())),
            headers={**headers, "Idempotency-Key": "job-create-key-0003"},
        )
        assert unusable.status_code == 409


def test_mask_job_requires_provider_capability(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'mask-capability.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap_tokens(database_url)
    provider_id = str(uuid4())
    seeded = _seed(
        database_url,
        provider_id,
        "success",
        "active",
        manual_mask=False,
    )
    body = {
        **_job_body(seeded, provider_id, candidates=1),
        "mask_asset_id": seeded["mask"],
    }

    with _client(database_url, tmp_path) as client:
        response = client.post(
            "/api/v1/jobs",
            json=body,
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "job-mask-unsupported-0001",
            },
        )

    assert response.status_code == 409
    assert response.json()["code"] == "provider_not_usable"


def test_offline_provider_creates_waiting_job(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'offline.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap_tokens(database_url)
    provider_id = str(uuid4())
    seeded = _seed(database_url, provider_id, "offline", "active")
    headers = {"Authorization": f"Bearer {tokens['app']}", "Idempotency-Key": "job-offline-key-001"}

    with _client(database_url, tmp_path) as client:
        created = client.post(
            "/api/v1/jobs", json=_job_body(seeded, provider_id, 1), headers=headers
        )
        assert created.status_code == 201, created.text
        job = created.json()
        assert job["state"] == "waiting_provider"
        assert job["block_reason"] == "provider_offline"
        assert job["items"][0]["state"] == "waiting_provider"
