import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.storage import StorageError, WorkflowArtifactStorage
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.providers.domain import ProviderCapabilities
from clothes_model.modules.workflows.application import canonical_json


def _bootstrap(database_url: str) -> str:
    async def run() -> str:
        runtime = create_database_runtime(database_url, 5000)
        try:
            credentials = await TokenService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions)
            ).bootstrap()
            return next(item.value for item in credentials if item.scope == "admin")
        finally:
            await runtime.close()

    return asyncio.run(run())


def _body(*, workflow_id: str = "try-on", version: int = 1) -> dict[str, object]:
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "person.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "garment.png"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 0, "candidate_index": 0, "person": ["1", 0]},
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    capabilities = ProviderCapabilities(
        max_candidates=1,
        source="workflow_declared",
        verification="declared",
    ).to_payload()
    manifest = {
        "schema_version": "1",
        "bindings": {
            "person": {"node_id": "1", "input": "image"},
            "garment": {"node_id": "2", "input": "image"},
            "seed": {"node_id": "3", "input": "seed"},
            "candidate_index": {"node_id": "3", "input": "candidate_index"},
        },
        "outputs": [{"node_id": "4", "output_index": 0}],
        "capabilities": capabilities,
    }
    return {
        "workflow_id": workflow_id,
        "version": version,
        "mode": "precise_try_on",
        "workflow_json": workflow,
        "manifest": manifest,
    }


def _client(tmp_path: Path) -> tuple[TestClient, str, Path]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'workflows.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    token = _bootstrap(database_url)
    storage_root = tmp_path / "storage"
    app = create_app(
        Settings(
            environment="test",
            product_release="v1_1",
            database_url=database_url,
            instance_lock_path=tmp_path / "instance.lock",
            storage_root=storage_root,
            admin_session_cookie_secure=False,
        )
    )
    return TestClient(app), token, storage_root


def test_workflow_create_read_restart_redaction_and_conflicts(tmp_path: Path) -> None:
    client_context, token, storage_root = _client(tmp_path)
    body = _body()
    with client_context as client:
        login = client.post("/api/v1/admin/auth/session", json={"admin_token": token})
        csrf = login.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-create-0001"}
        created = client.post("/api/v1/admin/workflows", json=body, headers=headers)
        assert created.status_code == 201, created.text
        payload = created.json()
        version_id = payload["id"]
        assert payload["state"] == "draft"
        assert payload["validation_status"] == "not_run"
        assert payload["artifacts"]["workflow_sha256"]
        assert "workflow_path" not in created.text
        assert "manifest_path" not in created.text
        replay = client.post("/api/v1/admin/workflows", json=body, headers=headers)
        assert replay.status_code == 201 and replay.json()["id"] == version_id
        conflict = client.post(
            "/api/v1/admin/workflows",
            json={**body, "workflow_json": {**body["workflow_json"], "5": {}}},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-create-0002"},
        )
        assert conflict.status_code == 409
        duplicate_artifact = client.post(
            "/api/v1/admin/workflows",
            json={**body, "workflow_id": "try-on-copy"},
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-create-0003"},
        )
        assert duplicate_artifact.status_code == 409
        artifact_directories = {
            item.name
            for item in (storage_root / "workflows").iterdir()
            if item.is_dir() and item.name != ".temporary"
        }
        assert artifact_directories == {version_id}
        listed = client.get("/api/v1/admin/workflows")
        assert listed.status_code == 200 and len(listed.json()["items"]) == 1
        assert client.get(f"/api/v1/admin/workflows/{version_id}").status_code == 200

    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'workflows.db').as_posix()}"
    with TestClient(
        create_app(
            Settings(
                environment="test",
                product_release="v1_1",
                database_url=database_url,
                instance_lock_path=tmp_path / "instance-2.lock",
                storage_root=storage_root,
                admin_session_cookie_secure=False,
            )
        )
    ) as restarted:
        login = restarted.post("/api/v1/admin/auth/session", json={"admin_token": token})
        assert login.status_code == 201
        assert restarted.get(f"/api/v1/admin/workflows/{version_id}").status_code == 200


def test_workflow_rejects_duplicate_keys_invalid_bindings_depth_and_size(tmp_path: Path) -> None:
    client_context, token, _ = _client(tmp_path)
    with client_context as client:
        login = client.post("/api/v1/admin/auth/session", json={"admin_token": token})
        csrf = login.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-invalid-0001"}
        duplicate = (
            '{"workflow_id":"a","workflow_id":"b","version":1,'
            '"mode":"precise_try_on","workflow_json":{},"manifest":{}}'
        )
        response = client.post(
            "/api/v1/admin/workflows",
            content=duplicate,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "workflow_json_duplicate_key"

        invalid = _body()
        manifest = dict(invalid["manifest"])
        bindings = dict(manifest["bindings"])
        bindings["person"] = {"node_id": "missing", "input": "image"}
        manifest["bindings"] = bindings
        invalid["manifest"] = manifest
        response = client.post(
            "/api/v1/admin/workflows",
            json=invalid,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workflow-invalid-0002"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "workflow_node_missing"

    nested: object = {}
    for _ in range(42):
        nested = {"next": nested}
    with pytest.raises(Exception, match="嵌套层级"):
        canonical_json(nested)
    with pytest.raises(Exception, match="超过安全上限"):
        canonical_json({"value": "x" * 2_000_001})


def test_workflow_storage_confinement_atomic_cleanup_and_digest_stability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = WorkflowArtifactStorage(tmp_path / "storage")
    first = canonical_json({"b": 2, "a": 1})
    second = canonical_json({"a": 1, "b": 2})
    assert first == second == b'{"a":1,"b":2}'
    stored = storage.publish("version-1", first, b"{}")
    assert storage.read(stored.workflow_path) == first
    with pytest.raises(StorageError):
        storage.read("../outside")
    with pytest.raises(StorageError):
        storage.publish("version-1", first, b"{}")
    assert storage.reconcile({"version-1"}) == []
    assert json.loads(storage.read(stored.manifest_path)) == {}

    failing = WorkflowArtifactStorage(tmp_path / "failing-storage")

    def fail_write(path: Path, content: bytes) -> None:
        del path, content
        raise OSError("simulated atomic write failure")

    monkeypatch.setattr(WorkflowArtifactStorage, "_write", staticmethod(fail_write))
    with pytest.raises(OSError, match="simulated atomic write failure"):
        failing.publish("version-2", first, b"{}")
    assert list(failing.temporary.iterdir()) == []
    assert not (failing.workflows / "version-2").exists()
