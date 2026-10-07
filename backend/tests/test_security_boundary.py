"""Consolidated V1 security boundary coverage for the release gate."""

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

ADMIN_GET_PATHS = [
    "/api/v1/admin/system/overview",
    "/api/v1/admin/configuration/retention",
    "/api/v1/admin/configuration/comfy-node",
    "/api/v1/admin/storage",
    "/api/v1/admin/diagnostics/jobs",
    "/api/v1/admin/provider-configs",
    "/api/v1/admin/workflows",
    "/api/v1/admin/app-credential",
]


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


def _build(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'security.db').as_posix()}"
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
    return TestClient(create_app(settings)), credentials


def test_app_token_cannot_reach_admin_routes(tmp_path: Path) -> None:
    client, credentials = _build(tmp_path)
    with client:
        for path in ADMIN_GET_PATHS:
            assert client.get(path).status_code == 401, path
            assert (
                client.get(
                    path, headers={"Authorization": f"Bearer {credentials['app']}"}
                ).status_code
                == 401
            ), path


def test_admin_session_cannot_reach_app_routes(tmp_path: Path) -> None:
    client, credentials = _build(tmp_path)
    with client:
        login = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": credentials["admin"]}
        )
        assert login.status_code == 201
        csrf = login.json()["csrf_token"]
        assert client.get("/api/v1/jobs").status_code == 401
        assert (
            client.post(
                "/api/v1/jobs",
                json={},
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "security-nope"},
            ).status_code
            == 401
        )


def test_overview_payload_contains_no_secret_material(tmp_path: Path) -> None:
    client, credentials = _build(tmp_path)
    with client:
        client.post("/api/v1/admin/auth/session", json={"admin_token": credentials["admin"]})
        response = client.get("/api/v1/admin/system/overview")
        assert response.status_code == 200
        lowered = response.text.lower()
        for forbidden in ("credential", "envelope", "secret", "authorization", "api_key"):
            assert forbidden not in lowered


def test_asset_content_requires_authentication(tmp_path: Path) -> None:
    client, _ = _build(tmp_path)
    with client:
        assert client.get("/api/v1/assets/does-not-exist/content").status_code == 401
