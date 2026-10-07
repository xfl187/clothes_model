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


def _config_body() -> dict[str, object]:
    return {
        "display_name": "Fake Provider",
        "type": "llm_image_edit",
        "adapter_type": "fake_image_edit",
        "endpoint": "https://fake.local",
        "model": "fake-model",
        "timeout_seconds": 30,
        "api_key": "raw-secret",
        "vendor_parameters": {"scenario": "success"},
    }


def test_provider_connection_test_is_free_and_requires_csrf(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'connection.db').as_posix()}"
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
    with TestClient(create_app(settings)) as client:
        login = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": credentials["admin"]}
        )
        csrf = login.json()["csrf_token"]
        created = client.post(
            "/api/v1/admin/provider-configs",
            json=_config_body(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "connection-create-0001"},
        )
        assert created.status_code == 201
        provider_id = created.json()["id"]

        assert (
            client.post(
                f"/api/v1/admin/provider-configs/{provider_id}/connection-test",
                headers={"Idempotency-Key": "connection-test-0001"},
            ).status_code
            == 403
        )
        tested = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/connection-test",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "connection-test-0001"},
        )
        assert tested.status_code == 200, tested.text
        assert tested.json()["status"] == "passed"
        assert {step["key"] for step in tested.json()["steps"]} == {
            "credentials",
            "connection",
            "capabilities",
        }
        listing = client.get("/api/v1/admin/provider-configs").json()
        assert listing["items"][0]["state"] == "inactive"
