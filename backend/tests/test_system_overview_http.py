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


def test_system_overview_requires_admin_and_aggregates(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'overview.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    key_path = tmp_path / "master.key"
    _master_key(key_path)
    credentials = _bootstrap(database_url)

    settings = Settings(
        environment="test",
        product_release="v1_1",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        encryption_master_key_file=key_path,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/system/overview").status_code == 401
        csrf = _login(client, credentials["admin"])
        assert csrf
        response = client.get("/api/v1/admin/system/overview")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["verdict"] in {"ok", "limited", "action_required", "unknown"}
        assert [dep["key"] for dep in body["dependencies"]] == [
            "business_service",
            "database",
            "storage",
            "comfyui",
        ]
        assert isinstance(body["blockers"], list)
        assert isinstance(body["action_items"], list)
        assert isinstance(body["effective_configuration"], dict)
        assert body["snapshot_at"]


def test_system_overview_reports_storage_degradation(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'overview2.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    key_path = tmp_path / "master.key"
    _master_key(key_path)
    credentials = _bootstrap(database_url)

    settings = Settings(
        environment="test",
        product_release="v1_1",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        encryption_master_key_file=key_path,
        storage_reserve_bytes=10**18,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        _login(client, credentials["admin"])
        body = client.get("/api/v1/admin/system/overview").json()
        storage = next(dep for dep in body["dependencies"] if dep["key"] == "storage")
        assert storage["state"] == "degraded"
        assert body["verdict"] == "limited"
