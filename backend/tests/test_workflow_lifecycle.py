import asyncio
import io
from pathlib import Path

import httpx2
from fastapi.testclient import TestClient
from PIL import Image

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.providers.domain import ProviderCapabilities


def _bootstrap(database_url: str) -> str:
    async def run() -> str:
        runtime = create_database_runtime(database_url, 5000)
        try:
            tokens = await TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions)).bootstrap()
            return next(item.value for item in tokens if item.scope == "admin")
        finally:
            await runtime.close()

    return asyncio.run(run())


def _workflow(version: int) -> dict[str, object]:
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "person.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "garment.png"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": version, "candidate_index": 0, "person": ["1", 0]},
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    manifest = {
        "schema_version": "1",
        "bindings": {
            "person": {"node_id": "1", "input": "image"},
            "garment": {"node_id": "2", "input": "image"},
            "seed": {"node_id": "3", "input": "seed"},
            "candidate_index": {"node_id": "3", "input": "candidate_index"},
        },
        "outputs": [{"node_id": "4", "output_index": 0}],
        "capabilities": ProviderCapabilities(
            max_candidates=1, source="workflow_declared", verification="declared"
        ).to_payload(),
    }
    return {
        "workflow_id": "try-on",
        "version": version,
        "mode": "precise_try_on",
        "workflow_json": workflow,
        "manifest": manifest,
    }


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color=(30, 60, 90)).save(buffer, "PNG")
    return buffer.getvalue()


def _settings(tmp_path: Path, *, lock_name: str = "instance.lock") -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'lifecycle.db').as_posix()}",
        instance_lock_path=tmp_path / lock_name,
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        comfy_node_allowed_hosts=["comfy.example"],
    )


def _app(tmp_path: Path, handler: object) -> tuple[object, str, httpx2.AsyncClient]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'lifecycle.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = _bootstrap(database_url)
    app = create_app(_settings(tmp_path))
    mock = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    app.state.comfy_http_client = mock
    return app, token, mock


def _compatible_objects() -> dict[str, object]:
    return {
        "LoadImage": {"input": {"required": {"image": ["STRING"]}}},
        "KSampler": {"input": {"required": {"seed": ["INT"], "candidate_index": ["INT"]}}},
        "SaveImage": {},
    }


def test_live_validation_activation_rollback_retirement_and_redaction(tmp_path: Path) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "0.3.60"}})
        if request.url.path == "/object_info":
            return httpx2.Response(
                200,
                json={
                    "LoadImage": {"input": {"required": {"image": ["STRING"]}}},
                    "KSampler": {
                        "input": {
                            "required": {
                                "seed": ["INT"],
                                "candidate_index": ["INT"],
                            }
                        }
                    },
                    "SaveImage": {},
                },
            )
        if request.url.path == "/upload/image":
            return httpx2.Response(200, json={"name": f"fixture-{len(seen_paths)}.png"})
        if request.url.path == "/prompt":
            return httpx2.Response(200, json={"prompt_id": "prompt-safe-id"})
        if request.url.path == "/history/prompt-safe-id":
            return httpx2.Response(
                200,
                json={
                    "prompt-safe-id": {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {
                            "4": {
                                "images": [
                                    {"filename": "result.png", "subfolder": "", "type": "temp"}
                                ]
                            }
                        },
                    }
                },
            )
        if request.url.path == "/view":
            return httpx2.Response(200, content=_png(), headers={"Content-Type": "image/png"})
        if request.url.path == "/api/clothes-model/temp" and request.method == "DELETE":
            return httpx2.Response(204)
        return httpx2.Response(404)

    app, token, mock = _app(tmp_path, handler)
    with TestClient(app) as client:
        login = client.post("/api/v1/admin/auth/session", json={"admin_token": token})
        csrf = login.json()["csrf_token"]
        node = client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={"endpoint": "https://comfy.example", "timeout_seconds": 2, "enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        assert node.status_code == 200
        version_ids: list[str] = []
        for version in (1, 2):
            created = client.post(
                "/api/v1/admin/workflows",
                json=_workflow(version),
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": f"create-lifecycle-{version}",
                },
            )
            assert created.status_code == 201, created.text
            version_ids.append(created.json()["id"])
            validated = client.post(
                f"/api/v1/admin/workflows/{version_ids[-1]}/validate",
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": f"validate-lifecycle-{version}",
                },
            )
            assert validated.status_code == 200, validated.text
            assert validated.json()["status"] == "passed"
            assert "prompt-safe-id" not in validated.text
            assert "fixture-" not in validated.text

        first = client.post(
            f"/api/v1/admin/workflows/{version_ids[0]}/activate",
            json={"confirm_new_jobs_only": True, "reason": "initial"},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "activate-lifecycle-1"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["state"] == "active"
        second = client.post(
            f"/api/v1/admin/workflows/{version_ids[1]}/activate",
            json={
                "confirm_new_jobs_only": True,
                "expected_current_active_workflow_version_id": version_ids[0],
                "reason": "upgrade",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "activate-lifecycle-2"},
        )
        assert second.status_code == 200, second.text
        assert second.json()["logical_provider_ref"]["revision"] == 3
        assert client.get(f"/api/v1/admin/workflows/{version_ids[0]}").json()["state"] == "retired"

        rolled_back = client.post(
            f"/api/v1/admin/workflows/{version_ids[0]}/activate",
            json={
                "confirm_new_jobs_only": True,
                "expected_current_active_workflow_version_id": version_ids[1],
                "reason": "rollback",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "rollback-lifecycle-1"},
        )
        assert rolled_back.status_code == 200, rolled_back.text
        assert rolled_back.json()["state"] == "active"
        retired = client.post(
            f"/api/v1/admin/workflows/{version_ids[0]}/retire",
            json={"confirm_new_jobs_only": True, "reason": "maintenance"},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "retire-lifecycle-1"},
        )
        assert retired.status_code == 200, retired.text
        assert retired.json()["state"] == "retired"
        assert "/api/clothes-model/temp" in seen_paths
    asyncio.run(mock.aclose())


def test_validation_reports_incompatible_node_and_cleanup_failure(tmp_path: Path) -> None:
    scenario = {"compatible": False}

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "test"}})
        if request.url.path == "/object_info":
            if not scenario["compatible"]:
                return httpx2.Response(200, json={"LoadImage": {}})
            return httpx2.Response(
                200, json={"LoadImage": {}, "KSampler": {}, "SaveImage": {}}
            )
        if request.url.path == "/upload/image":
            return httpx2.Response(200, json={"name": "safe.png"})
        if request.url.path == "/prompt":
            return httpx2.Response(200, json={"prompt_id": "safe"})
        if request.url.path == "/history/safe":
            return httpx2.Response(
                200,
                json={
                    "safe": {
                        "status": {"completed": True},
                        "outputs": {
                            "4": {
                                "images": [
                                    {"filename": "out.png", "subfolder": "", "type": "temp"}
                                ]
                            }
                        },
                    }
                },
            )
        if request.url.path == "/view":
            return httpx2.Response(200, content=_png(), headers={"Content-Type": "image/png"})
        if request.url.path == "/api/clothes-model/temp":
            return httpx2.Response(500)
        return httpx2.Response(404)

    app, token, mock = _app(tmp_path, handler)
    with TestClient(app) as client:
        csrf = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": token}
        ).json()["csrf_token"]
        client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={"endpoint": "https://comfy.example", "timeout_seconds": 1, "enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        created = client.post(
            "/api/v1/admin/workflows",
            json=_workflow(1),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-invalid-node"},
        ).json()
        incompatible = client.post(
            f"/api/v1/admin/workflows/{created['id']}/validate",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "validate-invalid-node"},
        )
        assert incompatible.status_code == 200
        assert incompatible.json()["compatibility"]["status"] == "incompatible"
        assert "KSampler" in incompatible.text

        scenario["compatible"] = True
        cleanup_failed = client.post(
            f"/api/v1/admin/workflows/{created['id']}/validate",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "validate-cleanup-fails"},
        )
        assert cleanup_failed.status_code == 200
        assert cleanup_failed.json()["status"] == "failed"
        assert any(
            item["key"] == "temporary_cleanup" and item["status"] == "failed"
            for item in cleanup_failed.json()["checks"]
        )
    asyncio.run(mock.aclose())


def test_validation_flags_missing_model_and_invalid_binding_input(tmp_path: Path) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "t"}})
        if request.url.path == "/object_info":
            return httpx2.Response(
                200,
                json={
                    "LoadImage": {"input": {"required": {"other": ["STRING"]}}},
                    "KSampler": {
                        "input": {
                            "required": {
                                "seed": ["INT"],
                                "candidate_index": ["INT"],
                                "ckpt_name": [["allowed.safetensors"]],
                            }
                        }
                    },
                    "SaveImage": {},
                },
            )
        return httpx2.Response(404)

    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "person.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "garment.png"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "candidate_index": 0,
                "ckpt_name": "other.safetensors",
            },
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    body = _workflow(1)
    body["workflow_json"] = workflow

    app, token, mock = _app(tmp_path, handler)
    with TestClient(app) as client:
        csrf = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": token}
        ).json()["csrf_token"]
        client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={"endpoint": "https://comfy.example", "timeout_seconds": 2, "enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        created = client.post(
            "/api/v1/admin/workflows",
            json=body,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-metadata-mismatch"},
        ).json()
        response = client.post(
            f"/api/v1/admin/workflows/{created['id']}/validate",
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "validate-metadata-mismatch"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["compatibility"]["status"] == "incompatible"
        keys = {item["key"] for item in response.json()["checks"] if item["status"] == "failed"}
        assert "required_model" in keys
        assert "binding_input" in keys
        assert "/prompt" not in seen_paths
    asyncio.run(mock.aclose())


def test_validation_reports_submit_execution_timeout_and_malformed_output(
    tmp_path: Path,
) -> None:
    scenario = {"mode": "submit_rejected"}

    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "t"}})
        if path == "/object_info":
            return httpx2.Response(200, json=_compatible_objects())
        if path == "/upload/image":
            return httpx2.Response(200, json={"name": "safe.png"})
        if path == "/prompt":
            if scenario["mode"] == "submit_rejected":
                return httpx2.Response(200, json={})
            return httpx2.Response(200, json={"prompt_id": "p1"})
        if path == "/history/p1":
            if scenario["mode"] == "timeout":
                return httpx2.Response(200, json={})
            if scenario["mode"] == "execution_failed":
                return httpx2.Response(
                    200,
                    json={
                        "p1": {
                            "status": {"completed": False, "status_str": "error"},
                            "outputs": {},
                        }
                    },
                )
            if scenario["mode"] == "malformed_output":
                return httpx2.Response(
                    200, json={"p1": {"status": {"completed": True}, "outputs": {}}}
                )
            return httpx2.Response(
                200,
                json={
                    "p1": {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {
                            "4": {
                                "images": [
                                    {"filename": "out.png", "subfolder": "", "type": "temp"}
                                ]
                            }
                        },
                    }
                },
            )
        if path == "/view":
            return httpx2.Response(200, content=_png(), headers={"Content-Type": "image/png"})
        if path == "/api/clothes-model/temp":
            return httpx2.Response(204)
        return httpx2.Response(404)

    expected = {
        "submit_rejected": "test_submit",
        "execution_failed": "test_execution",
        "timeout": "test_timeout",
        "malformed_output": "test_output",
    }
    app, token, mock = _app(tmp_path, handler)
    with TestClient(app) as client:
        csrf = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": token}
        ).json()["csrf_token"]
        client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={"endpoint": "https://comfy.example", "timeout_seconds": 1, "enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        created = client.post(
            "/api/v1/admin/workflows",
            json=_workflow(1),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-run-failures"},
        ).json()
        for mode, key in expected.items():
            scenario["mode"] = mode
            response = client.post(
                f"/api/v1/admin/workflows/{created['id']}/validate",
                headers={"X-CSRF-Token": csrf, "Idempotency-Key": f"validate-{mode}"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "failed"
            assert any(
                item["key"] == key and item["status"] == "failed"
                for item in response.json()["checks"]
            ), (mode, response.text)
    asyncio.run(mock.aclose())


def test_activation_rejects_stale_reference_and_restart_preserves_lifecycle(
    tmp_path: Path,
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "t"}})
        if path == "/object_info":
            return httpx2.Response(200, json=_compatible_objects())
        if path == "/upload/image":
            return httpx2.Response(200, json={"name": "safe.png"})
        if path == "/prompt":
            return httpx2.Response(200, json={"prompt_id": "p1"})
        if path == "/history/p1":
            return httpx2.Response(
                200,
                json={
                    "p1": {
                        "status": {"completed": True, "status_str": "success"},
                        "outputs": {
                            "4": {
                                "images": [
                                    {"filename": "out.png", "subfolder": "", "type": "temp"}
                                ]
                            }
                        },
                    }
                },
            )
        if path == "/view":
            return httpx2.Response(200, content=_png(), headers={"Content-Type": "image/png"})
        if path == "/api/clothes-model/temp":
            return httpx2.Response(204)
        return httpx2.Response(404)

    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'lifecycle.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = _bootstrap(database_url)
    app = create_app(_settings(tmp_path))
    mock = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    app.state.comfy_http_client = mock
    with TestClient(app) as client:
        csrf = client.post(
            "/api/v1/admin/auth/session", json={"admin_token": token}
        ).json()["csrf_token"]
        client.put(
            "/api/v1/admin/configuration/comfy-node",
            json={"endpoint": "https://comfy.example", "timeout_seconds": 2, "enabled": True},
            headers={"X-CSRF-Token": csrf},
        )
        first = client.post(
            "/api/v1/admin/workflows",
            json=_workflow(1),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-stale-1"},
        ).json()
        second = client.post(
            "/api/v1/admin/workflows",
            json=_workflow(2),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "create-stale-2"},
        ).json()
        for version, body in ((1, first), (2, second)):
            assert (
                client.post(
                    f"/api/v1/admin/workflows/{body['id']}/validate",
                    headers={"X-CSRF-Token": csrf, "Idempotency-Key": f"validate-stale-{version}"},
                ).status_code
                == 200
            )
        activated = client.post(
            f"/api/v1/admin/workflows/{first['id']}/activate",
            json={"confirm_new_jobs_only": True},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "activate-stale-1"},
        )
        assert activated.status_code == 200, activated.text
        stale_current = "00000000-0000-4000-8000-000000000099"
        stale = client.post(
            f"/api/v1/admin/workflows/{second['id']}/activate",
            json={
                "confirm_new_jobs_only": True,
                "expected_current_active_workflow_version_id": stale_current,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "activate-stale-2"},
        )
        assert stale.status_code == 409, stale.text
        assert stale.json()["code"] == "workflow_active_version_changed"

    restarted = create_app(_settings(tmp_path, lock_name="instance-2.lock"))
    restart_mock = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    restarted.state.comfy_http_client = restart_mock
    with TestClient(restarted) as client:
        login = client.post("/api/v1/admin/auth/session", json={"admin_token": token})
        assert login.status_code == 201
        current = client.get(f"/api/v1/admin/workflows/{first['id']}")
        assert current.status_code == 200
        assert current.json()["state"] == "active"
        assert current.json()["validated_at"] is not None
        assert client.get(f"/api/v1/admin/workflows/{second['id']}").json()["state"] == "draft"
    asyncio.run(mock.aclose())
    asyncio.run(restart_mock.aclose())
