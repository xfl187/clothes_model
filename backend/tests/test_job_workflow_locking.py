import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx2
from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.storage import WorkflowArtifactStorage
from clothes_model.modules.assets.domain import Asset, GarmentMetadata, PersonMetadata, StoredObject
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.comfy.domain import LOGICAL_COMFY_PROVIDER_ID, ComfyNodeConfig
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
)
from clothes_model.modules.workflows.application import canonical_json
from clothes_model.modules.workflows.domain import WorkflowVersion


def _now() -> datetime:
    return datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _bootstrap_tokens(database_url: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
            return {item.scope: item.value for item in await service.bootstrap()}
        finally:
            await runtime.close()

    return asyncio.run(run())


def _workflow(
    artifacts: WorkflowArtifactStorage,
    *,
    version: int = 1,
    categories: tuple[str, ...] = ("upper_body",),
    max_candidates: int = 2,
    requires_mask: bool = False,
) -> dict[str, object]:
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "person.png"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": "garment.png"}},
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": version, "candidate_index": 0, "person": ["1", 0]},
        },
        "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0]}},
    }
    bindings: dict[str, object] = {
        "person": {"node_id": "1", "input": "image"},
        "garment": {"node_id": "2", "input": "image"},
        "seed": {"node_id": "3", "input": "seed"},
        "candidate_index": {"node_id": "3", "input": "candidate_index"},
    }
    if requires_mask:
        workflow["5"] = {"class_type": "LoadImageMask", "inputs": {"image": "mask.png"}}
        bindings["mask"] = {"node_id": "5", "input": "image"}
    capabilities = ProviderCapabilities(
        garment_categories=categories,
        manual_mask=requires_mask,
        multiple_candidates=max_candidates > 1,
        region_mask=requires_mask,
        max_candidates=max_candidates,
        source="workflow_declared",
        verification="verified",
    ).to_payload()
    manifest = {
        "schema_version": "1",
        "bindings": bindings,
        "outputs": [{"node_id": "4", "output_index": 0}],
        "capabilities": capabilities,
    }
    version_id = str(uuid4())
    workflow_bytes = canonical_json(workflow)
    manifest_bytes = canonical_json(manifest)
    stored = artifacts.publish(version_id, workflow_bytes, manifest_bytes)
    return {
        "id": version_id,
        "version": version,
        "workflow": workflow,
        "manifest": manifest,
        "workflow_sha256": hashlib.sha256(workflow_bytes).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "stored": stored,
        "capabilities": capabilities,
    }


def _seed(
    database_url: str,
    artifacts: WorkflowArtifactStorage,
    *,
    node_enabled: bool = True,
    active: dict[str, object] | None = None,
    seed_provider: bool = True,
) -> dict[str, str]:
    person_id, garment_id = str(uuid4()), str(uuid4())
    person_object_id, garment_object_id = str(uuid4()), str(uuid4())
    provider_revision_id = str(uuid4())
    active_id = str(active["id"]) if active is not None else "unavailable"

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                for object_id, digest, content_type in (
                    (person_object_id, "b" * 64, "image/jpeg"),
                    (garment_object_id, "c" * 64, "image/jpeg"),
                ):
                    await uow.stored_objects.add(
                        StoredObject(
                            id=object_id,
                            sha256=digest,
                            relative_path=f"objects/{digest[0]}/{object_id}",
                            content_type=content_type,
                            size_bytes=128,
                            width=16,
                            height=8,
                            state="available",
                            asset_ref_count=0,
                            created_at=_now(),
                        )
                    )
                await uow.assets.add(
                    Asset(
                        id=person_id,
                        kind="person",
                        stored_object_id=person_object_id,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                        person=PersonMetadata(asset_id=person_id),
                    )
                )
                await uow.assets.add(
                    Asset(
                        id=garment_id,
                        kind="garment",
                        stored_object_id=garment_object_id,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                        garment=GarmentMetadata(
                            asset_id=garment_id, category="upper_body", source="photo"
                        ),
                    )
                )
                await uow.comfy_node.save(
                    ComfyNodeConfig(
                        id="default",
                        endpoint="https://comfy.example",
                        timeout_seconds=2,
                        enabled=node_enabled,
                        health_status="unchecked",
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )
                if seed_provider:
                    await uow.provider_configs.update_config(
                        ProviderConfig(
                            id=LOGICAL_COMFY_PROVIDER_ID,
                            display_name="ComfyUI",
                            provider_type="comfyui",
                            state="active",
                            created_at=_now(),
                            updated_at=_now(),
                        )
                    )
                    await uow.provider_configs.add_revision(
                        ProviderConfigRevision(
                            id=provider_revision_id,
                            provider_id=LOGICAL_COMFY_PROVIDER_ID,
                            revision=2,
                            adapter_type="comfyui",
                            endpoint="comfy://physical-node",
                            model="try-on:1",
                            timeout_seconds=2,
                            capabilities_json=json.dumps(
                                active["capabilities"] if active is not None else {}
                            ),
                            vendor_parameters_json=json.dumps(
                                {"workflow_version_id": active_id}
                            ),
                            created_at=_now(),
                        )
                    )
                if active is not None:
                    stored = active["stored"]
                    await uow.workflows.add(
                        WorkflowVersion(
                            id=str(active["id"]),
                            workflow_id="try-on",
                            version=int(active["version"]),
                            mode="precise_try_on",
                            display_name="try-on",
                            state="active",
                            workflow_sha256=str(active["workflow_sha256"]),
                            workflow_path=stored.workflow_path,
                            manifest_sha256=str(active["manifest_sha256"]),
                            manifest_path=stored.manifest_path,
                            bindings_schema_version="1",
                            manifest_json=json.dumps(active["manifest"]),
                            capabilities_json=json.dumps(active["capabilities"]),
                            created_at=_now(),
                            validated_at=_now(),
                            activated_at=_now(),
                        )
                    )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"person": person_id, "garment": garment_id}


def _settings(database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
        comfy_node_allowed_hosts=["comfy.example"],
    )


def _client(settings: Settings) -> tuple[TestClient, httpx2.AsyncClient]:
    app = create_app(settings)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/system_stats":
            return httpx2.Response(200, json={"system": {"comfyui_version": "test"}})
        return httpx2.Response(404)

    client = app.state.comfy_http_client
    client._transport = httpx2.MockTransport(handler)  # type: ignore[attr-defined]
    return TestClient(app), client


def _job_body(seeded: dict[str, str], candidates: int = 1) -> dict[str, object]:
    return {
        "person_asset_ids": [seeded["person"]],
        "garment_asset_id": seeded["garment"],
        "provider_id": LOGICAL_COMFY_PROVIDER_ID,
        "mode": "precise_try_on",
        "generation_options": {"candidate_count": candidates},
    }


def _setup(
    tmp_path: Path, **options: object
) -> tuple[Settings, dict[str, str], dict[str, object], dict[str, str]]:
    artifacts = WorkflowArtifactStorage(tmp_path / "storage")
    active = None
    if bool(options.get("seed_workflow", True)):
        active = _workflow(
            artifacts,
            categories=tuple(options.get("categories", ("upper_body",))),  # type: ignore[arg-type]
            max_candidates=int(options.get("max_candidates", 2)),
            requires_mask=bool(options.get("requires_mask", False)),
        )
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'locking.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens = _bootstrap_tokens(database_url)
    seeded = _seed(
        database_url,
        artifacts,
        node_enabled=bool(options.get("node_enabled", True)),
        active=active,
    )
    return _settings(database_url, tmp_path), seeded, active or {}, tokens


def test_comfy_job_locks_active_workflow(tmp_path: Path) -> None:
    settings, seeded, active, tokens = _setup(tmp_path)
    client, mock = _client(settings)
    with client:
        response = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-lock-0001",
            },
        )
        assert response.status_code == 201, response.text
        job = response.json()
        assert job["workflow_version_ref"]["workflow_version_id"] == active["id"]
        assert job["workflow_snapshot"]["workflow_sha256"] == active["workflow_sha256"]
        assert job["workflow_snapshot"]["manifest_sha256"] == active["manifest_sha256"]
        assert job["state"] == "queued"

        replay = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-lock-0001",
            },
        )
        assert replay.status_code == 201 and replay.json()["id"] == job["id"]
    asyncio.run(mock.aclose())


def test_comfy_job_rejected_without_active_workflow(tmp_path: Path) -> None:
    settings, seeded, _, tokens = _setup(tmp_path, seed_workflow=False)
    client, mock = _client(settings)
    with client:
        response = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-no-workflow",
            },
        )
        assert response.status_code == 409
        assert response.json()["code"] == "workflow_not_active"
    asyncio.run(mock.aclose())


def test_comfy_job_rejected_for_unsupported_category_and_mask(tmp_path: Path) -> None:
    settings, seeded, _, tokens = _setup(tmp_path, categories=("lower_body",))
    client, mock = _client(settings)
    with client:
        category = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-bad-category",
            },
        )
        assert category.status_code == 409
        assert category.json()["code"] == "workflow_incompatible"
    asyncio.run(mock.aclose())

    mask_tmp = tmp_path / "mask"
    mask_tmp.mkdir()
    mask_settings, mask_seeded, _, mask_tokens = _setup(mask_tmp, requires_mask=True)
    mask_client, mask_mock = _client(mask_settings)
    with mask_client:
        tokens = mask_tokens
        missing_mask = mask_client.post(
            "/api/v1/jobs",
            json=_job_body(mask_seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-missing-mask",
            },
        )
        assert missing_mask.status_code == 409
        assert missing_mask.json()["code"] == "workflow_incompatible"
    asyncio.run(mask_mock.aclose())


def test_comfy_job_offline_node_waits_with_locked_workflow(tmp_path: Path) -> None:
    settings, seeded, active, tokens = _setup(tmp_path, node_enabled=False)
    client, mock = _client(settings)
    with client:
        response = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-offline",
            },
        )
        assert response.status_code == 201, response.text
        job = response.json()
        assert job["state"] == "waiting_provider"
        assert job["block_reason"] == "provider_offline"
        assert job["workflow_version_ref"]["workflow_version_id"] == active["id"]
    asyncio.run(mock.aclose())


def test_later_activation_does_not_rewrite_locked_job(tmp_path: Path) -> None:
    settings, seeded, active, tokens = _setup(tmp_path)
    client, mock = _client(settings)
    with client:
        created = client.post(
            "/api/v1/jobs",
            json=_job_body(seeded),
            headers={
                "Authorization": f"Bearer {tokens['app']}",
                "Idempotency-Key": "comfy-isolation",
            },
        ).json()

        artifacts = WorkflowArtifactStorage(tmp_path / "storage")
        replacement = _workflow(artifacts, version=2)

        async def upgrade() -> None:
            runtime = create_database_runtime(settings.database_url, 5000)
            try:
                async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                    old = await uow.workflows.get(str(active["id"]))
                    assert old is not None
                    await uow.workflows.update_lifecycle(
                        replace(old, state="retired", retired_at=_now())
                    )
                    stored = replacement["stored"]
                    await uow.workflows.add(
                        WorkflowVersion(
                            id=str(replacement["id"]),
                            workflow_id="try-on",
                            version=2,
                            mode="precise_try_on",
                            display_name="try-on",
                            state="active",
                            workflow_sha256=str(replacement["workflow_sha256"]),
                            workflow_path=stored.workflow_path,
                            manifest_sha256=str(replacement["manifest_sha256"]),
                            manifest_path=stored.manifest_path,
                            bindings_schema_version="1",
                            manifest_json=json.dumps(replacement["manifest"]),
                            capabilities_json=json.dumps(replacement["capabilities"]),
                            created_at=_now(),
                            validated_at=_now(),
                            activated_at=_now(),
                        )
                    )
                    await uow.commit()
            finally:
                await runtime.close()

        asyncio.run(upgrade())

        fetched = client.get(
            f"/api/v1/jobs/{created['id']}",
            headers={"Authorization": f"Bearer {tokens['app']}"},
        ).json()
        assert fetched["workflow_version_ref"]["workflow_version_id"] == active["id"]
        assert fetched["workflow_snapshot"]["workflow_sha256"] == active["workflow_sha256"]
    asyncio.run(mock.aclose())
