import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError

from clothes_model.core.persistence import PersistenceConflict
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.database.models import (
    asset_references,
    assets,
    person_assets,
    security_audit_events,
    stored_objects,
)
from clothes_model.modules.assets.domain import (
    Asset,
    AssetReference,
    GarmentMetadata,
    IdempotencyRecord,
    PersonMetadata,
    StoredObject,
    UploadSession,
)
from clothes_model.modules.auth.domain import (
    AccessToken,
    AdminSession,
    AuthThrottle,
    SecurityAuditEvent,
)


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def now() -> datetime:
    return datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


def token(token_id: str, public_id: str) -> AccessToken:
    return AccessToken(
        id=token_id,
        public_id=public_id,
        secret_hash="$argon2id$v=19$fixture",
        scope="app",
        status="active",
        created_at=now(),
    )


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
        favorite=True,
        content_state="available",
        created_at=now(),
        updated_at=now(),
        garment=GarmentMetadata(
            asset_id=asset_id,
            category="upper_body",
            source="photo",
        ),
    )


def test_phase2_repositories_round_trip_and_uow_rollback(tmp_path: Path) -> None:
    database_path = tmp_path / "repositories.db"
    database_url = sqlite_url(database_path)
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.access_tokens.add(token("token-1", "public-1"))
                await uow.admin_sessions.add(
                    AdminSession(
                        id="session-1",
                        token_id="token-1",
                        session_digest="b" * 64,
                        csrf_digest="c" * 64,
                        state="active",
                        created_at=now(),
                        expires_at=now() + timedelta(hours=1),
                    )
                )
                await uow.auth_throttles.add(
                    AuthThrottle(
                        id="throttle-1",
                        throttle_key="network:fixture",
                        failed_count=1,
                        window_started_at=now(),
                        updated_at=now(),
                    )
                )
                await uow.idempotency.add(
                    IdempotencyRecord(
                        id="idem-1",
                        actor_scope="app",
                        actor_id="token-1",
                        operation="upload.create",
                        key_digest="d" * 64,
                        request_digest="e" * 64,
                        state="processing",
                        created_at=now(),
                        expires_at=now() + timedelta(days=1),
                    )
                )
                await uow.stored_objects.add(stored_object("object-1"))
                await uow.assets.add(person_asset("asset-1", "object-1"))
                await uow.uploads.add(
                    UploadSession(
                        id="upload-1",
                        actor_token_id="token-1",
                        asset_kind="person",
                        filename="person.jpg",
                        content_type="image/jpeg",
                        expected_size=128,
                        confirmed_offset=0,
                        temp_name="upload-1.part",
                        state="created",
                        created_at=now(),
                        expires_at=now() + timedelta(hours=2),
                    )
                )
                await uow.asset_references.add(
                    AssetReference(
                        id="reference-1",
                        asset_id="asset-1",
                        source_kind="test_fixture",
                        source_id="fixture-1",
                        active=True,
                        created_at=now(),
                    )
                )
                await uow.security_audit.add(
                    SecurityAuditEvent(
                        id="audit-1",
                        action="fixture.created",
                        actor_kind="app_token",
                        actor_id="token-1",
                        outcome="succeeded",
                        context_json='{"safe":true}',
                        created_at=now(),
                    )
                )
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                loaded_token = await uow.access_tokens.get_by_public_id("public-1")
                loaded_session = await uow.admin_sessions.get_by_digest("b" * 64)
                loaded_throttle = await uow.auth_throttles.get_by_key("network:fixture")
                loaded_idempotency = await uow.idempotency.get_bound(
                    "app", "token-1", "upload.create", "d" * 64
                )
                loaded_object = await uow.stored_objects.get_by_hash("a" * 64)
                loaded_asset = await uow.assets.get("asset-1")
                loaded_upload = await uow.uploads.get("upload-1")
                references = await uow.asset_references.list_active("asset-1")
                audit_count = await uow.session.scalar(
                    select(func.count()).select_from(security_audit_events)
                )

                assert loaded_token is not None and loaded_token.created_at.tzinfo is UTC
                assert loaded_session is not None and loaded_session.id == "session-1"
                assert loaded_throttle is not None and loaded_throttle.failed_count == 1
                assert loaded_idempotency is not None
                assert loaded_object is not None and loaded_object.asset_ref_count == 1
                assert loaded_asset is not None and loaded_asset.person is not None
                assert loaded_asset.garment is None
                assert loaded_upload is not None and loaded_upload.confirmed_offset == 0
                assert [reference.id for reference in references] == ["reference-1"]
                assert audit_count == 1

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.auth_throttles.add(
                    AuthThrottle(
                        id="rolled-back",
                        throttle_key="network:rollback",
                        failed_count=0,
                        window_started_at=now(),
                        updated_at=now(),
                    )
                )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert await uow.auth_throttles.get_by_key("network:rollback") is None
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_constraints_subtypes_references_and_shared_objects(tmp_path: Path) -> None:
    database_path = tmp_path / "constraints.db"
    database_url = sqlite_url(database_path)
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.stored_objects.add(stored_object("shared-object"))
                await uow.assets.add(person_asset("person-asset", "shared-object"))
                await uow.assets.add(garment_asset("garment-asset", "shared-object"))
                await uow.asset_references.add(
                    AssetReference(
                        id="blocker",
                        asset_id="person-asset",
                        source_kind="future_job",
                        source_id="future-1",
                        active=True,
                        created_at=now(),
                    )
                )
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        insert(person_assets).values(asset_id="garment-asset")
                    )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(PersistenceConflict, match="exactly one"):
                    await uow.assets.add(
                        Asset(
                            id="missing-subtype",
                            kind="person",
                            stored_object_id="shared-object",
                            favorite=False,
                            content_state="available",
                            created_at=now(),
                            updated_at=now(),
                        )
                    )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(delete(assets).where(assets.c.id == "person-asset"))

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(delete(assets).where(assets.c.id == "garment-asset"))
                await uow.commit()
            async with runtime.engine.connect() as connection:
                assert (
                    await connection.scalar(
                        select(stored_objects.c.asset_ref_count).where(
                            stored_objects.c.id == "shared-object"
                        )
                    )
                    == 1
                )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(
                    delete(asset_references).where(asset_references.c.id == "blocker")
                )
                await uow.session.execute(delete(assets).where(assets.c.id == "person-asset"))
                await uow.commit()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                assert await uow.stored_objects.get("shared-object") is not None
                await uow.session.execute(
                    delete(stored_objects).where(stored_objects.c.id == "shared-object")
                )
                await uow.commit()

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        insert(stored_objects).values(
                            id="invalid-object",
                            sha256="f" * 64,
                            relative_path="objects/invalid",
                            content_type="image/jpeg",
                            size_bytes=-1,
                            width=1,
                            height=1,
                            state="available",
                            asset_ref_count=0,
                            created_at=now(),
                        )
                    )

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                with pytest.raises(IntegrityError):
                    await uow.session.execute(
                        text(
                            "INSERT INTO admin_sessions "
                            "(id, token_id, session_digest, csrf_digest, state, "
                            "created_at, expires_at) VALUES "
                            "('orphan', 'missing', :session, :csrf, 'active', "
                            ":created, :expires)"
                        ),
                        {
                            "session": "1" * 64,
                            "csrf": "2" * 64,
                            "created": now().isoformat(),
                            "expires": (now() + timedelta(hours=1)).isoformat(),
                        },
                    )
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_duplicate_token_writers_translate_conflict(tmp_path: Path) -> None:
    database_path = tmp_path / "duplicates.db"
    database_url = sqlite_url(database_path)
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def exercise() -> None:
        runtime = create_database_runtime(database_url, 5000)
        ready = asyncio.Event()

        async def contender(token_id: str) -> str:
            await ready.wait()
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                try:
                    await uow.access_tokens.add(token(token_id, "same-public-id"))
                    await uow.commit()
                    return "committed"
                except PersistenceConflict:
                    await uow.rollback()
                    return "conflict"

        try:
            tasks = [
                asyncio.create_task(contender("token-a")),
                asyncio.create_task(contender("token-b")),
            ]
            ready.set()
            assert sorted(await asyncio.gather(*tasks)) == ["committed", "conflict"]
        finally:
            await runtime.close()

    asyncio.run(exercise())
