import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.assets.domain import Asset, PersonMetadata, StoredObject
from clothes_model.modules.auth.application import TokenService


def _now() -> datetime:
    return datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


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


def _seed_person(database_url: str) -> str:
    person_id, object_id = str(uuid4()), str(uuid4())

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.stored_objects.add(
                    StoredObject(
                        id=object_id,
                        sha256="e" * 64,
                        relative_path="objects/ee/person",
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
                        stored_object_id=object_id,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                        person=PersonMetadata(asset_id=person_id),
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return person_id


def _build(tmp_path: Path) -> tuple[TestClient, dict[str, str], str]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'outfits.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    credentials = _bootstrap(database_url)
    person_id = _seed_person(database_url)
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
    )
    return TestClient(create_app(settings)), credentials, person_id


def test_outfit_session_and_branch_lifecycle(tmp_path: Path) -> None:
    client, credentials, person_id = _build(tmp_path)
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        assert client.get("/api/v1/outfits").status_code == 401

        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": person_id, "name": "Look A"},
            headers={**headers, "Idempotency-Key": "outfit-create-0001"},
        )
        assert created.status_code == 201, created.text
        session = created.json()
        session_id = session["id"]
        assert session["name"] == "Look A"
        assert session["layer_definition_version"] == 1
        assert {t["key"] for t in session["layer_types"]} == {
            "inner_top",
            "outerwear",
            "lower_body",
            "dress",
        }
        assert len(session["branches"]) == 1
        main = session["branches"][0]
        assert main["is_mainline"] is True
        assert main["route"] == "split"

        listed = client.get("/api/v1/outfits", headers=headers).json()
        assert [item["id"] for item in listed["items"]] == [session_id]

        renamed = client.patch(
            f"/api/v1/outfits/{session_id}",
            json={"name": "Look B", "favorite": True},
            headers=headers,
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Look B"
        assert renamed.json()["favorite"] is True

        branched = client.post(
            f"/api/v1/outfits/{session_id}/branches",
            json={"name": "Dress route", "route": "dress"},
            headers={**headers, "Idempotency-Key": "outfit-branch-0001"},
        )
        assert branched.status_code == 201, branched.text
        branches = branched.json()["branches"]
        assert len(branches) == 2
        branch_id = next(b for b in branches if not b["is_mainline"])["id"]

        promoted = client.patch(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}",
            json={"mainline": True},
            headers=headers,
        )
        assert promoted.status_code == 200
        branches_after = promoted.json()["branches"]
        assert next(b for b in branches_after if b["id"] == branch_id)["is_mainline"] is True
        assert next(b for b in branches_after if b["id"] == main["id"])["is_mainline"] is False

        deleted = client.delete(
            f"/api/v1/outfits/{session_id}/branches/{main['id']}", headers=headers
        )
        assert deleted.status_code == 200, deleted.text
        assert len(deleted.json()["branches"]) == 1

        assert client.delete(f"/api/v1/outfits/{session_id}", headers=headers).status_code == 204
        assert client.get(f"/api/v1/outfits/{session_id}", headers=headers).status_code == 404


def test_outfit_delete_guards_single_branch(tmp_path: Path) -> None:
    client, credentials, person_id = _build(tmp_path)
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": person_id},
            headers={**headers, "Idempotency-Key": "outfit-create-0002"},
        ).json()
        session_id = created["id"]
        main_branch_id = created["branches"][0]["id"]
        blocked = client.delete(
            f"/api/v1/outfits/{session_id}/branches/{main_branch_id}", headers=headers
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "outfit_single_branch"
