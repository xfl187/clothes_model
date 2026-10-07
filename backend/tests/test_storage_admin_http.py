import asyncio
import base64
import os
from pathlib import Path
from uuid import uuid4

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


def test_storage_retention_scan_and_cleanup(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'storage.db').as_posix()}"
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
        assert client.get("/api/v1/admin/configuration/retention").status_code == 401
        csrf = _login(client, credentials["admin"])

        retention = client.get("/api/v1/admin/configuration/retention")
        assert retention.status_code == 200, retention.text
        assert retention.json()["unfavorited_output_days"] == 30
        assert retention.json()["intermediate_file_days"] == 7

        updated = client.put(
            "/api/v1/admin/configuration/retention",
            json={"unfavorited_output_days": 14, "intermediate_file_days": 3},
            headers={"X-CSRF-Token": csrf},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["unfavorited_output_days"] == 14

        storage = client.get("/api/v1/admin/storage")
        assert storage.status_code == 200
        body = storage.json()
        assert body["accepting_new_work"] is True
        assert body["state"] in {"healthy", "warning", "blocked", "unknown"}
        assert {"capacity_bytes", "used_bytes", "available_bytes", "checked_at"} <= set(body)

        scan = client.post(
            "/api/v1/admin/storage/scan",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "scan-0002"},
        )
        assert scan.status_code == 200, scan.text
        scan_id = scan.json()["scan_id"]
        assert scan.json()["reclaimable_files"] == 0

        bad = client.post(
            "/api/v1/admin/storage/cleanup",
            json={"scan_id": str(uuid4()), "confirm_irreversible": True},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "cleanup-bad"},
        )
        assert bad.status_code == 409

        cleanup = client.post(
            "/api/v1/admin/storage/cleanup",
            json={"scan_id": scan_id, "confirm_irreversible": True},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "cleanup-ok"},
        )
        assert cleanup.status_code == 200, cleanup.text
        assert cleanup.json()["deleted_files"] == 0
