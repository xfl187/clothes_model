import asyncio
import base64
import os
from pathlib import Path

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.security import AesGcmSecretCipher
from clothes_model.modules.auth.application import TokenService


def _master_key(path: Path) -> None:
    path.write_text(base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"), encoding="ascii")


def _bootstrap(database_url: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
            return {item.scope: item.value for item in await service.bootstrap()}
        finally:
            await runtime.close()

    return asyncio.run(run())


def _config_body(
    scenario: str = "success", api_key: str | None = "raw-secret"
) -> dict[str, object]:
    return {
        "display_name": "Fake Provider",
        "type": "llm_image_edit",
        "adapter_type": "fake_image_edit",
        "endpoint": "https://fake.local",
        "model": "fake-model",
        "timeout_seconds": 30,
        "api_key": api_key,
        "vendor_parameters": {"scenario": scenario},
    }


def test_provider_config_lifecycle_and_app_availability(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'providers.db').as_posix()}"
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
        assert login.status_code == 201
        csrf = login.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "provider-create-key-0001"}

        created = client.post(
            "/api/v1/admin/provider-configs", json=_config_body(), headers=headers
        )
        assert created.status_code == 201
        config = created.json()
        provider_id = config["id"]
        assert config["secret_configured"] is True
        assert config["state"] == "inactive"
        assert "raw-secret" not in created.text
        assert "api_key" not in config

        disposable = client.post(
            "/api/v1/admin/provider-configs",
            json=_config_body(api_key="disposable-secret"),
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "provider-create-disposable-0001",
            },
        )
        assert disposable.status_code == 201
        disposable_id = disposable.json()["id"]
        deleted = client.delete(
            f"/api/v1/admin/provider-configs/{disposable_id}",
            headers={"X-CSRF-Token": csrf},
        )
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/admin/provider-configs/{disposable_id}").status_code == 404

        replay = client.post(
            "/api/v1/admin/provider-configs", json=_config_body(), headers=headers
        )
        assert replay.status_code == 201 and replay.json()["id"] == provider_id

        conflict = client.post(
            "/api/v1/admin/provider-configs",
            json=_config_body(api_key="other"),
            headers=headers,
        )
        assert conflict.status_code == 409

        assert client.get(f"/api/v1/admin/provider-configs/{provider_id}").status_code == 200

        updated = client.patch(
            f"/api/v1/admin/provider-configs/{provider_id}",
            json=_config_body(api_key=None),
            headers={"X-CSRF-Token": csrf},
        )
        assert updated.status_code == 200
        assert updated.json()["config_ref"]["revision"] == 2
        assert updated.json()["secret_configured"] is True

        validated = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/validate",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "provider-validate-0001"},
        )
        assert validated.status_code == 200
        assert validated.json()["status"] == "passed"
        assert [step["key"] for step in validated.json()["steps"]] == [
            "credentials",
            "connection",
            "capabilities",
            "generation",
            "output_decode",
        ]

        enabled = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/enable",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "provider-enable-0001"},
        )
        assert enabled.status_code == 200
        assert enabled.json()["state"] == "active"

        default = client.put(
            "/api/v1/admin/configuration/default-provider",
            json={"provider_id": provider_id, "confirm_new_jobs_only": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert default.status_code == 200, default.text
        assert default.json()["provider_id"] == provider_id

        default_archive = client.post(
            f"/api/v1/admin/provider-configs/{provider_id}/archive",
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "provider-archive-default-0001",
            },
        )
        assert default_archive.status_code == 409
        assert default_archive.json()["code"] == "provider_is_default"

        available = client.get(
            "/api/v1/providers", headers={"Authorization": f"Bearer {credentials['app']}"}
        )
        assert available.status_code == 200
        items = available.json()["items"]
        assert items and items[0]["availability"] == "available"
        assert items[0]["is_default"] is True
        assert items[0]["capabilities"]["manual_mask"]["supported"] is True

        client.app.state.secret_cipher = AesGcmSecretCipher(os.urandom(32))
        degraded = client.get(
            "/api/v1/providers", headers={"Authorization": f"Bearer {credentials['app']}"}
        )
        assert degraded.status_code == 200
        assert degraded.json()["items"][0]["availability"] == "unavailable_configuration"
        assert degraded.json()["items"][0]["unavailable_reason"] == (
            "Provider 凭据无法用当前服务端主密钥解密，请管理员重新保存 API Key。"
        )

        default_delete = client.delete(
            f"/api/v1/admin/provider-configs/{provider_id}",
            headers={"X-CSRF-Token": csrf},
        )
        assert default_delete.status_code == 409
        assert default_delete.json()["code"] == "provider_is_default"
