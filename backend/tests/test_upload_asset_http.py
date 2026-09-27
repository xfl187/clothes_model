import asyncio
import hashlib
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.auth.application import TokenService


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 6), (120, 30, 80)).save(output, format="PNG")
    return output.getvalue()


def app_token(database_url: str) -> str:
    async def create() -> str:
        runtime = create_database_runtime(database_url, 5000)
        try:
            issued = await TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions)).bootstrap()
            return next(item.value for item in issued if item.scope == "app")
        finally:
            await runtime.close()

    return asyncio.run(create())


def test_resumable_upload_asset_catalog_private_content_and_delete(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'assets.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = app_token(database_url)
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_root=tmp_path / "storage",
        instance_lock_path=tmp_path / "instance.lock",
        admin_session_cookie_secure=False,
        storage_reserve_bytes=0,
    )
    headers = {"Authorization": f"Bearer {token}"}
    content = png_bytes()
    with TestClient(create_app(settings)) as client:
        create_headers = {**headers, "Idempotency-Key": "create-fixture-0001"}
        payload = {
            "asset_kind": "person",
            "filename": "person.png",
            "content_type": "image/png",
            "size_bytes": len(content),
        }
        created = client.post("/api/v1/uploads", headers=create_headers, json=payload)
        assert created.status_code == 201
        assert (
            client.post("/api/v1/uploads", headers=create_headers, json=payload).json()
            == created.json()
        )
        upload_id = created.json()["id"]
        assert (
            client.patch(
                f"/api/v1/uploads/{upload_id}/content",
                headers={
                    **headers,
                    "Upload-Offset": "1",
                    "Content-Type": "application/offset+octet-stream",
                },
                content=content,
            ).status_code
            == 409
        )
        midpoint = len(content) // 2
        for offset, chunk in ((0, content[:midpoint]), (midpoint, content[midpoint:])):
            response = client.patch(
                f"/api/v1/uploads/{upload_id}/content",
                headers={
                    **headers,
                    "Upload-Offset": str(offset),
                    "Content-Type": "application/offset+octet-stream",
                },
                content=chunk,
            )
            assert response.status_code == 200
        completed = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers={**headers, "Idempotency-Key": "complete-fixture-0001"},
            json={"sha256": hashlib.sha256(content).hexdigest()},
        )
        assert completed.status_code == 201
        asset_id = completed.json()["id"]
        replay = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers={**headers, "Idempotency-Key": "complete-fixture-0001"},
            json={"sha256": hashlib.sha256(content).hexdigest()},
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == asset_id
        mismatched_replay = client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            headers={**headers, "Idempotency-Key": "complete-fixture-0001"},
            json={"sha256": "0" * 64},
        )
        assert mismatched_replay.status_code == 409
        assert mismatched_replay.json()["code"] == "idempotency_key_reused"
        assert client.get("/api/v1/assets").status_code == 401
        listing = client.get("/api/v1/assets", headers=headers).json()
        assert [item["id"] for item in listing["items"]] == [asset_id]
        assert client.patch(
            f"/api/v1/assets/{asset_id}", headers=headers, json={"favorite": True}
        ).json()["favorite"]
        downloaded = client.get(f"/api/v1/assets/{asset_id}/content", headers=headers)
        assert (
            downloaded.status_code == 200
            and downloaded.headers["cache-control"] == "private, no-store"
        )
        deleted = client.delete(f"/api/v1/assets/{asset_id}/content", headers=headers)
        assert deleted.status_code == 200 and not deleted.json()["asset"]["content_available"]
        assert client.get(f"/api/v1/assets/{asset_id}/content", headers=headers).status_code == 404


def test_capacity_guard_returns_507(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'capacity.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = app_token(database_url)
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_root=tmp_path / "storage",
        instance_lock_path=tmp_path / "lock",
        admin_session_cookie_secure=False,
        storage_reserve_bytes=10**18,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "capacity-1"},
            json={
                "asset_kind": "person",
                "filename": "x.png",
                "content_type": "image/png",
                "size_bytes": 100,
            },
        )
        assert response.status_code == 507


def test_restart_truncates_uncommitted_upload_bytes(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'restart.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = app_token(database_url)
    settings = Settings(
        environment="test",
        database_url=database_url,
        storage_root=tmp_path / "storage",
        instance_lock_path=tmp_path / "lock",
        admin_session_cookie_secure=False,
        storage_reserve_bytes=0,
    )
    headers = {"Authorization": f"Bearer {token}"}
    content = png_bytes()
    midpoint = len(content) // 2
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/v1/uploads",
            headers={**headers, "Idempotency-Key": "restart-create"},
            json={
                "asset_kind": "person",
                "filename": "restart.png",
                "content_type": "image/png",
                "size_bytes": len(content),
            },
        )
        upload_id = created.json()["id"]
        appended = client.patch(
            f"/api/v1/uploads/{upload_id}/content",
            headers={**headers, "Upload-Offset": "0"},
            content=content[:midpoint],
        )
        assert appended.status_code == 200

    temporary = settings.storage_root / "temp" / f"{upload_id}.part"
    with temporary.open("ab") as handle:
        handle.write(b"uncommitted")
    assert temporary.stat().st_size > midpoint

    with TestClient(create_app(settings)) as client:
        assert temporary.stat().st_size == midpoint
        status = client.get(f"/api/v1/uploads/{upload_id}", headers=headers)
        assert status.json()["uploaded_bytes"] == midpoint
