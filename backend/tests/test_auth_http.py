import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.auth.application import TokenService


def test_app_and_admin_auth_cookie_csrf_logout_and_throttle(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'auth.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")

    async def bootstrap() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
            return {item.scope: item.value for item in await service.bootstrap()}
        finally:
            await runtime.close()

    credentials = asyncio.run(bootstrap())
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        admin_session_cookie_secure=False,
        admin_login_max_failures=2,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/auth/status").status_code == 401
        app_status = client.get(
            "/api/v1/auth/status", headers={"Authorization": f"Bearer {credentials['app']}"}
        )
        assert app_status.status_code == 200
        assert credentials["app"] not in app_status.text

        assert client.get("/api/v1/assets").status_code == 401
        assert (
            client.get(
                "/api/v1/assets",
                headers={"Authorization": f"Bearer {credentials['app']}"},
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/api/v1/admin/storage",
                headers={"Authorization": f"Bearer {credentials['app']}"},
            ).status_code
            == 401
        )

        login = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": credentials["admin"]}
        )
        assert login.status_code == 201
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        csrf = login.json()["csrf_token"]
        assert client.get("/api/v1/admin/storage").status_code == 200
        assert client.post("/api/v1/admin/storage/scan").status_code == 403
        assert (
            client.post(
                "/api/v1/admin/storage/scan",
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": "scan-0001"},
            ).status_code
            == 200
        )
        assert (
            client.delete(
                "/api/v1/admin/auth/session", headers={"X-CSRF-Token": "wrong"}
            ).status_code
            == 403
        )
        assert (
            client.delete("/api/v1/admin/auth/session", headers={"X-CSRF-Token": csrf}).status_code
            == 204
        )
        assert client.get("/api/v1/admin/auth/session").status_code == 401

        for expected in (401, 401, 429):
            response = client.post("/api/v1/admin/auth/session", json={"admin_token": "x" * 32})
            assert response.status_code == expected
            assert "x" * 32 not in response.text


def test_production_rejects_insecure_admin_cookie() -> None:
    with pytest.raises(ValueError, match="secure Admin session"):
        Settings(environment="production", admin_session_cookie_secure=False)


def test_expired_admin_login_throttle_window_resets_existing_row(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'expired-throttle.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        admin_session_cookie_secure=False,
        admin_login_window_seconds=30,
    )
    throttle_key = "admin-login:" + hashlib.sha256(b"testclient").hexdigest()[:24]

    with TestClient(create_app(settings)) as client:
        assert (
            client.post("/api/v1/admin/auth/session", json={"admin_token": "x" * 32}).status_code
            == 401
        )

        async def expire_window() -> None:
            runtime = create_database_runtime(database_url, 5000)
            try:
                async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                    throttle = await uow.auth_throttles.get_by_key(throttle_key)
                    assert throttle is not None
                    expired_at = datetime.now(UTC) - timedelta(seconds=31)
                    await uow.auth_throttles.replace(
                        replace(
                            throttle,
                            window_started_at=expired_at,
                            updated_at=expired_at,
                        )
                    )
                    await uow.commit()
            finally:
                await runtime.close()

        asyncio.run(expire_window())

        response = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": "y" * 32}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "unauthorized"
