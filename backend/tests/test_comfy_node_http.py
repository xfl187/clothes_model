import asyncio
import base64
import os
from pathlib import Path

import httpx2
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


def test_comfy_node_secret_retention_redaction_probe_and_idempotency(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'comfy.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    key_path = tmp_path / "master.key"
    _master_key(key_path)
    credentials = _bootstrap(database_url)
    seen_authorization: list[str | None] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_authorization.append(request.headers.get("authorization"))
        if request.url.path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "0.3.50"}})
        if request.url.path == "/object_info":
            return httpx2.Response(200, json={"LoadImage": {}, "SaveImage": {}})
        return httpx2.Response(404)

    settings = Settings(
        environment="test",
        product_release="v1_1",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        encryption_master_key_file=key_path,
        comfy_node_allowed_hosts=["comfy.example"],
    )
    app = create_app(settings)
    mock_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    app.state.comfy_http_client = mock_client
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/configuration/comfy-node").status_code == 401
        assert (
            client.get(
                "/api/v1/admin/configuration/comfy-node",
                headers={"Authorization": f"Bearer {credentials['app']}"},
            ).status_code
            == 401
        )
        csrf = _login(client, credentials["admin"])
        body = {
            "endpoint": "https://comfy.example",
            "credential": "top-secret",
            "timeout_seconds": 30,
            "enabled": True,
        }
        assert client.put("/api/v1/admin/configuration/comfy-node", json=body).status_code == 403
        saved = client.put(
            "/api/v1/admin/configuration/comfy-node",
            json=body,
            headers={"X-CSRF-Token": csrf},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["credential_configured"] is True
        assert "top-secret" not in saved.text
        assert "credential" not in saved.json()

        retained = client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={key: value for key, value in body.items() if key != "credential"},
            headers={"X-CSRF-Token": csrf},
        )
        assert retained.status_code == 200
        assert retained.json()["credential_configured"] is True

        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "comfy-probe-0001"}
        tested = client.post("/api/v1/admin/configuration/comfy-node/test", headers=headers)
        assert tested.status_code == 200, tested.text
        assert tested.json()["status"] == "passed"
        replay = client.post("/api/v1/admin/configuration/comfy-node/test", headers=headers)
        assert replay.status_code == 200
        assert replay.json()["status"] == "passed"
        assert len(seen_authorization) == 2
        assert seen_authorization == ["Bearer top-secret", "Bearer top-secret"]

        current = client.get("/api/v1/admin/configuration/comfy-node")
        assert current.status_code == 200
        assert current.json()["health"] == "healthy"
        assert current.json()["observed_server_version"] == "0.3.50"
        assert "top-secret" not in current.text
    asyncio.run(mock_client.aclose())


def test_comfy_node_rejects_untrusted_host_and_missing_secret_store(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'comfy-reject.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    credentials = _bootstrap(database_url)
    settings = Settings(
        environment="test",
        product_release="v1_1",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        comfy_node_allowed_hosts=["comfy.example"],
    )
    with TestClient(create_app(settings)) as client:
        csrf = _login(client, credentials["admin"])
        base = {"timeout_seconds": 30, "enabled": True}
        rejected = client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={**base, "endpoint": "https://169.254.169.254"},
            headers={"X-CSRF-Token": csrf},
        )
        assert rejected.status_code == 422
        assert rejected.json()["code"] == "comfy_endpoint_host_rejected"
        missing_key = client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={
                **base,
                "endpoint": "https://comfy.example",
                "credential": "raw-node-credential-value",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert missing_key.status_code == 409
        assert missing_key.json()["code"] == "secret_store_unavailable"
        assert "raw-node-credential-value" not in missing_key.text


def test_comfy_probe_maps_redirect_timeout_and_malformed_responses(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'comfy-probe-errors.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    key_path = tmp_path / "master.key"
    _master_key(key_path)
    credentials = _bootstrap(database_url)
    scenario = {"value": "redirect"}

    def handler(request: httpx2.Request) -> httpx2.Response:
        del request
        if scenario["value"] == "redirect":
            return httpx2.Response(302, headers={"Location": "https://evil.example"})
        if scenario["value"] == "timeout":
            raise httpx2.ConnectTimeout("safe-test-timeout")
        return httpx2.Response(200, text="not-json")

    settings = Settings(
        environment="test",
        product_release="v1_1",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        encryption_master_key_file=key_path,
        comfy_node_allowed_hosts=["comfy.example"],
    )
    app = create_app(settings)
    mock_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    app.state.comfy_http_client = mock_client
    with TestClient(app) as client:
        csrf = _login(client, credentials["admin"])
        saved = client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={
                "endpoint": "https://comfy.example",
                "credential": "probe-secret-value",
                "timeout_seconds": 1,
                "enabled": True,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert saved.status_code == 200
        for index, (value, expected_health) in enumerate(
            (("redirect", "offline"), ("timeout", "offline"), ("malformed", "incompatible"))
        ):
            scenario["value"] = value
            tested = client.post(
                "/api/v1/admin/configuration/comfy-node/test",
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": f"probe-error-{index}",
                },
            )
            assert tested.status_code == 200
            assert tested.json()["status"] == "failed"
            current = client.get("/api/v1/admin/configuration/comfy-node")
            assert current.json()["health"] == expected_health
            assert "probe-secret-value" not in tested.text
            assert "safe-test-timeout" not in tested.text
            assert "not-json" not in tested.text
    asyncio.run(mock_client.aclose())
