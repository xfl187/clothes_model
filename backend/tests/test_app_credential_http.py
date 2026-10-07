import asyncio
import base64
import os
from pathlib import Path

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.auth.application import TokenService


def _master_key(path: Path) -> None:
    path.write_text(base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"), encoding="ascii")


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


def _login(client: TestClient, token: str) -> str:
    response = client.post("/api/v1/admin/auth/session", json={"admin_token": token})
    assert response.status_code == 201
    return str(response.json()["csrf_token"])


def test_app_credential_metadata_and_one_time_rotation(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'credential.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    key_path = tmp_path / "master.key"
    _master_key(key_path)
    credentials = _bootstrap(database_url)

    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        encryption_master_key_file=key_path,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/app-credential").status_code == 401
        csrf = _login(client, credentials["admin"])

        metadata = client.get("/api/v1/admin/app-credential")
        assert metadata.status_code == 200, metadata.text
        old_public_id = metadata.json()["token_id"]
        assert metadata.json()["status"] == "active"

        assert (
            client.post(
                "/api/v1/admin/app-credential",
                headers={"Idempotency-Key": "rotate-00000001"},
            ).status_code
            == 403
        )

        rotated = client.post(
            "/api/v1/admin/app-credential",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rotate-00000001"},
        )
        assert rotated.status_code == 200, rotated.text
        new_token = rotated.json()["token"]
        assert new_token
        assert rotated.json()["token_id"] != old_public_id

        replay = client.post(
            "/api/v1/admin/app-credential",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rotate-00000001"},
        )
        assert replay.status_code == 409
        assert new_token not in replay.text

        assert (
            client.get(
                "/api/v1/auth/status",
                headers={"Authorization": f"Bearer {credentials['app']}"},
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/v1/auth/status",
                headers={"Authorization": f"Bearer {new_token}"},
            ).status_code
            == 200
        )
