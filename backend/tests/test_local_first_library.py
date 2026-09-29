"""Owner isolation and 24-hour input-binary cleanup for the local-first library."""

import asyncio
import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import insert, select

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database import models as db
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.security import Argon2TokenHasher, generate_token
from clothes_model.infrastructure.storage.local import LocalFileStorage
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.cleanup.service import (
    cleanup_due_assets,
    schedule_eligible_assets,
)
from clothes_model.modules.providers.domain import ProviderCapabilities


def _now() -> datetime:
    return datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def _png(color: tuple[int, int, int] = (120, 30, 80)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), color).save(output, format="PNG")
    return output.getvalue()


def _settings(database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        storage_root=tmp_path / "storage",
        instance_lock_path=tmp_path / "instance.lock",
        admin_session_cookie_secure=False,
        storage_reserve_bytes=0,
    )


def _bootstrap_app_token(database_url: str) -> str:
    async def run() -> str:
        runtime = create_database_runtime(database_url, 5000)
        try:
            issued = await TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions)).bootstrap()
        finally:
            await runtime.close()
        return next(item.value for item in issued if item.scope == "app")

    return asyncio.run(run())


def _rotate_app_token(database_url: str) -> str:
    async def run() -> str:
        runtime = create_database_runtime(database_url, 5000)
        try:
            issued = await TokenService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions)
            ).rotate_app()
        finally:
            await runtime.close()
        return issued.value

    return asyncio.run(run())


def _create_second_owner_token(database_url: str) -> tuple[str, str]:
    async def run() -> tuple[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            generated = generate_token("app")
            hasher = Argon2TokenHasher()
            owner_id = str(uuid4())
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                now = _now()
                await uow.session.execute(
                    insert(db.owner_scopes).values(id=owner_id, created_at=now)
                )
                await uow.session.execute(
                    insert(db.access_tokens).values(
                        id=str(uuid4()),
                        public_id=generated.public_id,
                        secret_hash=hasher.hash(generated.secret),
                        scope="app",
                        owner_scope_id=owner_id,
                        status="active",
                        created_at=now,
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()
        return generated.value, owner_id

    return asyncio.run(run())


def _seed_assets_and_provider(database_url: str, provider_id: str) -> dict[str, str]:
    person_id, garment_id = str(uuid4()), str(uuid4())
    person_object_id, garment_object_id = str(uuid4()), str(uuid4())
    revision_id = str(uuid4())

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                now = _now()
                owner_id = await uow.session.scalar(
                    select(db.owner_scopes.c.id).limit(1)
                )
                for object_id, sha, path, content_type in (
                    (person_object_id, "b" * 64, "objects/bb/person.jpg", "image/jpeg"),
                    (garment_object_id, "c" * 64, "objects/cc/garment.jpg", "image/jpeg"),
                ):
                    await uow.session.execute(
                        insert(db.stored_objects).values(
                            id=object_id,
                            sha256=sha,
                            relative_path=path,
                            content_type=content_type,
                            size_bytes=128,
                            width=16,
                            height=8,
                            state="available",
                            asset_ref_count=0,
                            created_at=now,
                        )
                    )
                await uow.session.execute(
                    insert(db.assets).values(
                        id=person_id,
                        kind="person",
                        owner_scope_id=owner_id,
                        stored_object_id=person_object_id,
                        favorite=False,
                        content_state="available",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.session.execute(
                    insert(db.person_assets).values(asset_id=person_id)
                )
                await uow.session.execute(
                    insert(db.assets).values(
                        id=garment_id,
                        kind="garment",
                        owner_scope_id=owner_id,
                        stored_object_id=garment_object_id,
                        favorite=False,
                        content_state="available",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.session.execute(
                    insert(db.garment_assets).values(
                        asset_id=garment_id, category="upper_body", source="photo"
                    )
                )
                await uow.session.execute(
                    insert(db.provider_configs).values(
                        id=provider_id,
                        display_name="Fake Provider",
                        provider_type="llm_image_edit",
                        state="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await uow.session.execute(
                    insert(db.provider_config_revisions).values(
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
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"person": person_id, "garment": garment_id, "provider": provider_id}


async def _add_asset_with_content(
    uow: SqlAlchemyUnitOfWork,
    *,
    owner_id: str,
    kind: str,
    sha256: str,
    relative_path: str,
    durable: bool,
    cleanup_after: datetime | None,
    reuse_object_id: str | None = None,
) -> tuple[str, str]:
    object_id, asset_id = reuse_object_id or str(uuid4()), str(uuid4())
    now = _now()
    if reuse_object_id is None:
        await uow.session.execute(
            insert(db.stored_objects).values(
                id=object_id,
                sha256=sha256,
                relative_path=relative_path,
                content_type="image/jpeg",
                size_bytes=64,
                width=8,
                height=6,
                state="available",
                asset_ref_count=0,
                created_at=now,
            )
        )
    await uow.session.execute(
        insert(db.assets).values(
            id=asset_id,
            kind=kind,
            owner_scope_id=owner_id,
            stored_object_id=object_id,
            favorite=False,
            content_state="available",
            durable_client_copy_confirmed=durable,
            cleanup_after=cleanup_after,
            created_at=now,
            updated_at=now,
        )
    )
    if kind == "person":
        await uow.session.execute(insert(db.person_assets).values(asset_id=asset_id))
    elif kind == "garment":
        await uow.session.execute(
            insert(db.garment_assets).values(
                asset_id=asset_id, category="upper_body", source="photo"
            )
        )
    return asset_id, object_id


async def _insert_active_job(
    uow: SqlAlchemyUnitOfWork, *, owner_id: str, asset_id: str, state: str = "running"
) -> str:
    provider_id, revision_id, job_id = str(uuid4()), str(uuid4()), str(uuid4())
    now = _now()
    await uow.session.execute(
        insert(db.provider_configs).values(
            id=provider_id,
            display_name="Fake Provider",
            provider_type="llm_image_edit",
            state="active",
            created_at=now,
            updated_at=now,
        )
    )
    await uow.session.execute(
        insert(db.provider_config_revisions).values(
            id=revision_id,
            provider_id=provider_id,
            revision=1,
            adapter_type="fake_image_edit",
            endpoint="https://fake.local",
            model="fake-model",
            timeout_seconds=30,
            capabilities_json="{}",
            vendor_parameters_json="{}",
            created_at=now,
        )
    )
    await uow.session.execute(
        insert(db.jobs).values(
            id=job_id,
            owner_scope_id=owner_id,
            mode="precise_try_on",
            state=state,
            candidate_count=1,
            garment_asset_id=asset_id,
            provider_id=provider_id,
            provider_revision_id=revision_id,
            provider_snapshot_json="{}",
            advanced_parameters_json="{}",
            created_at=now,
            updated_at=now,
        )
    )
    await uow.session.execute(
        insert(db.asset_references).values(
            id=str(uuid4()),
            asset_id=asset_id,
            source_kind="job",
            source_id=job_id,
            display_label="试穿任务",
            active=True,
            created_at=now,
        )
    )
    return job_id


def test_auth_status_exposes_stable_identity_across_token_rotation(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'identity.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = _bootstrap_app_token(database_url)
    with TestClient(create_app(_settings(database_url, tmp_path))) as client:
        first = client.get(
            "/api/v1/auth/status", headers={"Authorization": f"Bearer {token}"}
        ).json()
    assert first["server_instance_id"] is not None
    assert first["owner_scope_id"] is not None

    rotated = _rotate_app_token(database_url)
    with TestClient(create_app(_settings(database_url, tmp_path))) as client:
        second = client.get(
            "/api/v1/auth/status", headers={"Authorization": f"Bearer {rotated}"}
        ).json()
        assert (
            client.get(
                "/api/v1/auth/status", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 401
        )
    assert second["owner_scope_id"] == first["owner_scope_id"]
    assert second["server_instance_id"] == first["server_instance_id"]


def test_second_owner_cannot_reach_first_owner_assets_or_jobs(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'isolation.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token_a = _bootstrap_app_token(database_url)
    seeded = _seed_assets_and_provider(database_url, str(uuid4()))
    token_b, owner_b = _create_second_owner_token(database_url)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    with TestClient(create_app(_settings(database_url, tmp_path))) as client:
        status_a = client.get("/api/v1/auth/status", headers=headers_a).json()
        asset_a = seeded["person"]

        assert client.get("/api/v1/assets", headers=headers_b).json()["items"] == []
        assert client.get(f"/api/v1/assets/{asset_a}", headers=headers_b).status_code == 404
        assert (
            client.patch(
                f"/api/v1/assets/{asset_a}", headers=headers_b, json={"favorite": True}
            ).status_code
            == 404
        )
        assert (
            client.get(f"/api/v1/assets/{asset_a}/content", headers=headers_b).status_code == 404
        )
        assert (
            client.get(f"/api/v1/assets/{asset_a}/references", headers=headers_b).status_code
            == 404
        )
        assert (
            client.delete(f"/api/v1/assets/{asset_a}/content", headers=headers_b).status_code
            == 404
        )
        assert (
            client.put(
                f"/api/v1/assets/{asset_a}/local-copy",
                headers=headers_b,
                json={"client_asset_id": str(uuid4()), "sha256": "b" * 64},
            ).status_code
            == 404
        )

        foreign_job = client.post(
            "/api/v1/jobs",
            headers={**headers_b, "Idempotency-Key": "foreign-job-0001"},
            json={
                "person_asset_ids": [seeded["person"]],
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "mode": "precise_try_on",
                "generation_options": {"candidate_count": 1},
            },
        )
        assert foreign_job.status_code == 422
        assert client.get("/api/v1/jobs", headers=headers_b).json()["items"] == []

        status_b = client.get("/api/v1/auth/status", headers=headers_b).json()
        assert status_b["owner_scope_id"] == owner_b
        assert status_b["owner_scope_id"] != status_a["owner_scope_id"]


def test_local_copy_ack_requires_matching_hash_and_sets_cleanup(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'ack.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = _bootstrap_app_token(database_url)
    headers = {"Authorization": f"Bearer {token}"}
    content = _png()
    with TestClient(create_app(_settings(database_url, tmp_path))) as client:
        created = client.post(
            "/api/v1/uploads",
            headers={**headers, "Idempotency-Key": "ack-create-0001"},
            json={
                "asset_kind": "person",
                "filename": "person.png",
                "content_type": "image/png",
                "size_bytes": len(content),
            },
        )
        upload_id = created.json()["id"]
        client.patch(
            f"/api/v1/uploads/{upload_id}/content",
            headers={**headers, "Upload-Offset": "0"},
            content=content,
        )
        completed = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers={**headers, "Idempotency-Key": "ack-complete-0001"},
            json={"sha256": hashlib.sha256(content).hexdigest()},
        )
        asset = completed.json()
        asset_id, sha = asset["id"], asset["content_sha256"]
        assert asset["durable_client_copy_confirmed"] is False
        assert asset["cleanup_after"] is None

        mismatched = client.put(
            f"/api/v1/assets/{asset_id}/local-copy",
            headers=headers,
            json={"client_asset_id": str(uuid4()), "sha256": "0" * 64},
        )
        assert mismatched.status_code == 409

        acknowledged = client.put(
            f"/api/v1/assets/{asset_id}/local-copy",
            headers=headers,
            json={"client_asset_id": str(uuid4()), "sha256": sha},
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["durable_client_copy_confirmed"] is True
        assert acknowledged.json()["cleanup_after"] is not None


def test_active_job_reference_protects_input_bytes(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'protect.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    storage = LocalFileStorage(tmp_path / "storage")

    async def scenario() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            owner_id = str(uuid4())
            now = _now()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    insert(db.owner_scopes).values(id=owner_id, created_at=now)
                )
                await uow.commit()
                asset_id, _object_id = await _add_asset_with_content(
                    uow,
                    owner_id=owner_id,
                    kind="person",
                    sha256=hashlib.sha256(_png()).hexdigest(),
                    relative_path="objects/aa/person.jpg",
                    durable=True,
                    cleanup_after=now - timedelta(hours=1),
                )
                await _insert_active_job(uow, owner_id=owner_id, asset_id=asset_id)
                await uow.commit()

            scheduled = await schedule_eligible_assets(runtime.sessions, now=now)
            assert scheduled == 0
            summary = await cleanup_due_assets(runtime.sessions, storage, now=now)
            assert summary.deleted_files == 0
            assert summary.skipped_protected_files == 1

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                row = (
                    await uow.session.execute(
                        select(db.assets.c.content_state, db.assets.c.cleanup_after).where(
                            db.assets.c.id == asset_id
                        )
                    )
                ).one()
            assert row.content_state == "available"
            assert row.cleanup_after is None
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_cleanup_after_deadline_removes_binary_but_keeps_logical_asset(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'cleanup.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    storage = LocalFileStorage(tmp_path / "storage")

    async def scenario() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            owner_id = str(uuid4())
            now = _now()
            normalized = storage.normalize_and_store(_png((10, 20, 30)))
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    insert(db.owner_scopes).values(id=owner_id, created_at=now)
                )
                asset_id, object_id = await _add_asset_with_content(
                    uow,
                    owner_id=owner_id,
                    kind="garment",
                    sha256=normalized.sha256,
                    relative_path=normalized.relative_path,
                    durable=True,
                    cleanup_after=now - timedelta(hours=1),
                )
                await uow.commit()

            not_due = await cleanup_due_assets(
                runtime.sessions, storage, now=now - timedelta(hours=2)
            )
            assert not_due.deleted_files == 0

            summary = await cleanup_due_assets(runtime.sessions, storage, now=now)
            assert summary.deleted_files == 1
            assert summary.reclaimed_bytes > 0
            assert not (tmp_path / "storage" / normalized.relative_path).exists()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                asset = (
                    await uow.session.execute(
                        select(db.assets.c.content_state, db.assets.c.stored_object_id).where(
                            db.assets.c.id == asset_id
                        )
                    )
                ).one()
                object_row = (
                    await uow.session.execute(
                        select(db.stored_objects.c.id).where(db.stored_objects.c.id == object_id)
                    )
                ).one_or_none()
            assert asset.content_state == "deleted"
            assert asset.stored_object_id is None
            assert object_row is None
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_unacknowledged_legacy_asset_is_never_scheduled_or_cleaned(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    storage = LocalFileStorage(tmp_path / "storage")

    async def scenario() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            owner_id = str(uuid4())
            now = _now()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    insert(db.owner_scopes).values(id=owner_id, created_at=now)
                )
                asset_id, _object_id = await _add_asset_with_content(
                    uow,
                    owner_id=owner_id,
                    kind="person",
                    sha256=hashlib.sha256(_png()).hexdigest(),
                    relative_path="objects/aa/legacy.jpg",
                    durable=False,
                    cleanup_after=None,
                )
                await uow.commit()

            assert await schedule_eligible_assets(runtime.sessions, now=now) == 0
            summary = await cleanup_due_assets(
                runtime.sessions, storage, now=now + timedelta(days=30)
            )
            assert summary.deleted_files == 0

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                row = (
                    await uow.session.execute(
                        select(
                            db.assets.c.content_state, db.assets.c.cleanup_after
                        ).where(db.assets.c.id == asset_id)
                    )
                ).one()
            assert row.content_state == "available"
            assert row.cleanup_after is None
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_shared_stored_object_kept_while_another_asset_is_available(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'shared.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    storage = LocalFileStorage(tmp_path / "storage")

    async def scenario() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            owner_id = str(uuid4())
            now = _now()
            normalized = storage.normalize_and_store(_png((44, 55, 66)))
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    insert(db.owner_scopes).values(id=owner_id, created_at=now)
                )
                _, object_id = await _add_asset_with_content(
                    uow,
                    owner_id=owner_id,
                    kind="person",
                    sha256=normalized.sha256,
                    relative_path=normalized.relative_path,
                    durable=True,
                    cleanup_after=now - timedelta(hours=1),
                )
                kept_asset, kept_object_id = await _add_asset_with_content(
                    uow,
                    owner_id=owner_id,
                    kind="garment",
                    sha256=normalized.sha256,
                    relative_path=normalized.relative_path,
                    durable=False,
                    cleanup_after=None,
                    reuse_object_id=object_id,
                )
                await uow.commit()

            summary = await cleanup_due_assets(runtime.sessions, storage, now=now)
            assert summary.deleted_files == 0
            assert (tmp_path / "storage" / normalized.relative_path).exists()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                kept = (
                    await uow.session.execute(
                        select(db.assets.c.content_state).where(db.assets.c.id == kept_asset)
                    )
                ).one()
                object_row = (
                    await uow.session.execute(
                        select(db.stored_objects.c.id).where(db.stored_objects.c.id == object_id)
                    )
                ).one_or_none()
            assert kept.content_state == "available"
            assert kept_object_id == object_id
            assert object_row is not None
        finally:
            await runtime.close()

    asyncio.run(scenario())


def test_rehydrating_cleaned_content_reuses_the_same_logical_asset(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'rehydrate.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    storage = LocalFileStorage(tmp_path / "storage")
    token = _bootstrap_app_token(database_url)
    headers = {"Authorization": f"Bearer {token}"}
    original = _png((90, 10, 40))
    replacement = _png((10, 90, 40))

    with TestClient(create_app(_settings(database_url, tmp_path))) as client:
        created = client.post(
            "/api/v1/uploads",
            headers={**headers, "Idempotency-Key": "rehydrate-create-0001"},
            json={
                "asset_kind": "person",
                "filename": "person.png",
                "content_type": "image/png",
                "size_bytes": len(original),
            },
        )
        upload_id = created.json()["id"]
        client.patch(
            f"/api/v1/uploads/{upload_id}/content",
            headers={**headers, "Upload-Offset": "0"},
            content=original,
        )
        completed = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers={**headers, "Idempotency-Key": "rehydrate-complete-0001"},
            json={"sha256": hashlib.sha256(original).hexdigest()},
        )
        asset_id = completed.json()["id"]

    async def clean_asset() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    db.assets.update()
                    .where(db.assets.c.id == asset_id)
                    .values(
                        durable_client_copy_confirmed=True,
                        cleanup_after=_now() - timedelta(hours=1),
                    )
                )
                await uow.commit()
            await cleanup_due_assets(runtime.sessions, storage, now=_now())
        finally:
            await runtime.close()

    asyncio.run(clean_asset())

    with TestClient(create_app(_settings(database_url, tmp_path))) as client:
        assert client.get(f"/api/v1/assets/{asset_id}", headers=headers).json()[
            "content_available"
        ] is False
        created = client.post(
            "/api/v1/uploads",
            headers={**headers, "Idempotency-Key": "rehydrate-create-0002"},
            json={
                "asset_kind": "person",
                "filename": "person.png",
                "content_type": "image/png",
                "size_bytes": len(replacement),
                "target_asset_id": asset_id,
            },
        )
        assert created.status_code == 201, created.text
        upload_id = created.json()["id"]
        client.patch(
            f"/api/v1/uploads/{upload_id}/content",
            headers={**headers, "Upload-Offset": "0"},
            content=replacement,
        )
        completed = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers={**headers, "Idempotency-Key": "rehydrate-complete-0002"},
            json={"sha256": hashlib.sha256(replacement).hexdigest()},
        )
        assert completed.status_code == 201, completed.text
        assert completed.json()["id"] == asset_id
        assert completed.json()["content_available"] is True
        assert completed.json()["cleanup_after"] is None
