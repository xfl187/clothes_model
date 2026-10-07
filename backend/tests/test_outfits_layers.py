import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.assets.domain import (
    Asset,
    GarmentMetadata,
    PersonMetadata,
    StoredObject,
)
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.jobs.domain import GeneratedOutputRecord
from clothes_model.modules.providers.domain import ProviderConfig, ProviderConfigRevision

_ALL_ROLES = ["inner_top", "outerwear", "lower_body", "dress"]


def _now() -> datetime:
    return datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def _capabilities(*, sequential: bool) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "garment_categories": {
                "values": ["upper_body", "lower_body", "dress"],
                "source": "adapter",
                "verification": "declared",
            },
            "manual_mask": {"supported": True, "source": "adapter", "verification": "declared"},
            "sequential_layering": {
                "supported": sequential,
                "source": "adapter",
                "verification": "declared",
            },
            "supported_layer_roles": {
                "values": _ALL_ROLES,
                "source": "adapter",
                "verification": "declared",
            },
            "output_constraints": {"max_candidates": 4},
        }
    )


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


def _seed_assets_and_provider(
    database_url: str, *, sequential: bool = True, adapter_type: str = "fake_image_edit"
) -> dict[str, str]:
    person_id, garment_id = str(uuid4()), str(uuid4())
    provider_id, revision_id = str(uuid4()), str(uuid4())
    person_object, garment_object = str(uuid4()), str(uuid4())

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                for object_id, digest, path in (
                    (person_object, "e", "objects/ee/person"),
                    (garment_object, "f", "objects/ff/garment"),
                ):
                    await uow.stored_objects.add(
                        StoredObject(
                            id=object_id,
                            sha256=digest * 64,
                            relative_path=path,
                            content_type="image/jpeg",
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
                        stored_object_id=person_object,
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
                        stored_object_id=garment_object,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                        garment=GarmentMetadata(
                            asset_id=garment_id, category="upper_body", source="photo"
                        ),
                    )
                )
                await uow.provider_configs.add_config(
                    ProviderConfig(
                        id=provider_id,
                        display_name="Layered Fake",
                        provider_type="llm_image_edit",
                        state="active",
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )
                await uow.provider_configs.add_revision(
                    ProviderConfigRevision(
                        id=revision_id,
                        provider_id=provider_id,
                        revision=1,
                        adapter_type=adapter_type,
                        endpoint="https://fake.local",
                        model="fake-model",
                        timeout_seconds=30,
                        capabilities_json=_capabilities(sequential=sequential),
                        vendor_parameters_json='{"scenario":"success"}',
                        created_at=_now(),
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return {"person": person_id, "garment": garment_id, "provider": provider_id}


def _seed_output(database_url: str, job_item_id: str) -> str:
    output_id, asset_id, object_id = str(uuid4()), str(uuid4()), str(uuid4())
    digest = uuid4().hex + uuid4().hex
    relative_path = f"objects/{uuid4().hex}/output"

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.stored_objects.add(
                    StoredObject(
                        id=object_id,
                        sha256=digest,
                        relative_path=relative_path,
                        content_type="image/png",
                        size_bytes=256,
                        width=16,
                        height=16,
                        state="available",
                        asset_ref_count=1,
                        created_at=_now(),
                    )
                )
                await uow.assets.add(
                    Asset(
                        id=asset_id,
                        kind="generated_output",
                        stored_object_id=object_id,
                        favorite=False,
                        content_state="available",
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )
                await uow.job_outputs.add_output(
                    GeneratedOutputRecord(
                        id=output_id,
                        job_item_id=job_item_id,
                        asset_id=asset_id,
                        favorite=False,
                        seed=None,
                        actual_parameters_json="{}",
                        quality_warnings_json="[]",
                        created_at=_now(),
                    )
                )
                await uow.commit()
        finally:
            await runtime.close()

    asyncio.run(run())
    return output_id


def _build(
    tmp_path: Path, *, sequential: bool = True, adapter_type: str = "fake_image_edit"
) -> tuple[TestClient, dict, dict]:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'outfit-layers.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    credentials = _bootstrap(database_url)
    seeded = _seed_assets_and_provider(
        database_url, sequential=sequential, adapter_type=adapter_type
    )
    settings = Settings(
        environment="test",
        database_url=database_url,
        instance_lock_path=tmp_path / "instance.lock",
        storage_root=tmp_path / "storage",
        admin_session_cookie_secure=False,
    )
    return TestClient(create_app(settings)), credentials, seeded


def test_add_layer_creates_job_and_select_commits_revision(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path)
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'outfit-layers.db').as_posix()}"
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-session-0001"},
        ).json()
        session_id = created["id"]
        branch_id = created["branches"][0]["id"]
        base_revision = created["head_revision"]["id"]

        layered = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers",
            json={
                "role": "inner_top",
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "candidate_count": 1,
            },
            headers={**headers, "Idempotency-Key": "ol-layer-0001"},
        )
        assert layered.status_code == 201, layered.text
        result = layered.json()
        job_id = result["job"]["id"]
        item_id = result["job"]["items"][0]["id"]
        assert result["job"]["garment_asset_id"] == seeded["garment"]
        assert "workflow_version_ref" not in result["job"]  # non-Comfy job stays Workflow-free

        output_id = _seed_output(database_url, item_id)
        selected = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}"
            f"/revisions/{base_revision}/select",
            json={"job_item_id": item_id, "output_id": output_id},
            headers={**headers, "Idempotency-Key": "ol-select-0001"},
        )
        assert selected.status_code == 200, selected.text
        head = selected.json()["head_revision"]
        assert head["id"] != base_revision
        assert [layer["role"] for layer in head["layers"]] == ["inner_top"]
        assert head["layers"][0]["selected_output_id"] == output_id
        assert job_id  # the linked job existed


def test_remove_layer_marks_later_layers_pending_without_new_jobs(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path)
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'outfit-layers.db').as_posix()}"
    headers = {"Authorization": f"Bearer {credentials['app']}"}

    def job_count() -> int:
        import sqlite3

        with sqlite3.connect(tmp_path / "outfit-layers.db") as connection:
            return int(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-rm-session"},
        ).json()
        session_id = created["id"]
        branch_id = created["branches"][0]["id"]
        base = created["head_revision"]["id"]

        def add(role: str, key: str) -> tuple[str, str]:
            response = client.post(
                f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers",
                json={
                    "role": role,
                    "garment_asset_id": seeded["garment"],
                    "provider_id": seeded["provider"],
                    "candidate_count": 1,
                },
                headers={**headers, "Idempotency-Key": key},
            )
            assert response.status_code == 201, response.text
            payload = response.json()
            item_id = payload["job"]["items"][0]["id"]
            layer_id = payload["session"]["branches"][0]["layers"][-1]["id"]
            return item_id, layer_id

        def select(item_id: str, revision: str, key: str) -> dict:
            output_id = _seed_output(database_url, item_id)
            response = client.post(
                f"/api/v1/outfits/{session_id}/branches/{branch_id}/revisions/{revision}/select",
                json={"job_item_id": item_id, "output_id": output_id},
                headers={**headers, "Idempotency-Key": key},
            )
            assert response.status_code == 200, response.text
            return response.json()

        item1, layer1 = add("inner_top", "ol-rm-l1")
        session = select(item1, base, "ol-rm-s1")
        revision1 = session["head_revision"]["id"]

        item2, layer2 = add("lower_body", "ol-rm-l2")
        session = select(item2, revision1, "ol-rm-s2")
        roles = {layer["role"]: layer["state"] for layer in session["branches"][0]["layers"]}
        assert roles == {"inner_top": "applied", "lower_body": "applied"}
        jobs_before = job_count()

        removed = client.request(
            "DELETE",
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer1}",
            json={"mode": "remove"},
            headers=headers,
        )
        assert removed.status_code == 200, removed.text
        remaining = removed.json()["branches"][0]["layers"]
        assert [layer["role"] for layer in remaining] == ["lower_body"]
        assert remaining[0]["state"] == "pending_reapply"
        assert remaining[0]["id"] == layer2
        assert job_count() == jobs_before  # the modification created no task

        reverted = client.request(
            "DELETE",
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer2}",
            json={"mode": "revert"},
            headers=headers,
        )
        assert reverted.status_code == 200
        after = reverted.json()["branches"][0]["layers"]
        assert [layer["state"] for layer in after] == ["pending_reapply"]


def test_switch_route_preserves_outerwear_without_new_jobs(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path)
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'outfit-layers.db').as_posix()}"
    headers = {"Authorization": f"Bearer {credentials['app']}"}

    def job_count() -> int:
        import sqlite3

        with sqlite3.connect(tmp_path / "outfit-layers.db") as connection:
            return int(connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-route-session"},
        ).json()
        session_id = created["id"]
        branch_id = created["branches"][0]["id"]

        layer = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers",
            json={
                "role": "outerwear",
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "candidate_count": 1,
            },
            headers={**headers, "Idempotency-Key": "ol-route-outer"},
        ).json()
        item_id = layer["job"]["items"][0]["id"]
        output_id = _seed_output(database_url, item_id)
        applied = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/revisions/"
            f"{created['head_revision']['id']}/select",
            json={"job_item_id": item_id, "output_id": output_id},
            headers={**headers, "Idempotency-Key": "ol-route-select"},
        ).json()
        assert applied["branches"][0]["layers"][0]["state"] == "applied"
        jobs_before = job_count()

        switched = client.post(
            f"/api/v1/outfits/{session_id}/route",
            json={"route": "dress"},
            headers={**headers, "Idempotency-Key": "ol-route-switch"},
        )
        assert switched.status_code == 200, switched.text
        branches = switched.json()["branches"]
        assert len(branches) == 2
        new_branch = next(b for b in branches if b["route"] == "dress")
        assert [layer["role"] for layer in new_branch["layers"]] == ["outerwear"]
        assert new_branch["layers"][0]["state"] == "pending_reapply"
        original = next(b for b in branches if b["id"] == branch_id)
        assert original["layers"][0]["state"] == "applied"  # original branch unchanged
        assert job_count() == jobs_before  # switching created no task


def _disable_provider(database_url: str, provider_id: str) -> None:
    import sqlite3

    path = database_url.split("///", 1)[1]
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_configs SET state='disabled' WHERE id=?", (provider_id,)
        )
        connection.commit()


def test_reapply_requires_explicit_provider_and_never_silently_switches(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path)
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'outfit-layers.db').as_posix()}"
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-re-session"},
        ).json()
        session_id = created["id"]
        branch_id = created["branches"][0]["id"]
        layer = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers",
            json={
                "role": "outerwear",
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "candidate_count": 1,
            },
            headers={**headers, "Idempotency-Key": "ol-re-outer"},
        ).json()
        layer_id = layer["session"]["branches"][0]["layers"][0]["id"]
        first_job = layer["job"]["id"]

        explicit = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}/reapply",
            json={"provider_id": seeded["provider"], "candidate_count": 1},
            headers={**headers, "Idempotency-Key": "ol-re-explicit"},
        )
        assert explicit.status_code == 201, explicit.text
        assert explicit.json()["job"]["id"] != first_job

        _disable_provider(database_url, seeded["provider"])
        blocked = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}/reapply",
            json={"candidate_count": 1},
            headers={**headers, "Idempotency-Key": "ol-re-blocked"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "provider_not_usable"


def test_outfit_layer_references_protect_and_release_assets(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path)
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-ref-session"},
        ).json()
        session_id = created["id"]
        branch_id = created["branches"][0]["id"]
        layer = client.post(
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers",
            json={
                "role": "inner_top",
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "candidate_count": 1,
            },
            headers={**headers, "Idempotency-Key": "ol-ref-layer"},
        ).json()
        layer_id = layer["session"]["branches"][0]["layers"][0]["id"]

        references = client.get(
            f"/api/v1/assets/{seeded['garment']}/references", headers=headers
        ).json()["items"]
        assert any(ref["source_kind"] == "outfit" for ref in references)

        blocked = client.delete(f"/api/v1/assets/{seeded['garment']}/content", headers=headers)
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "asset_referenced"

        client.request(
            "DELETE",
            f"/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}",
            json={"mode": "remove"},
            headers=headers,
        )
        released = client.get(
            f"/api/v1/assets/{seeded['garment']}/references", headers=headers
        ).json()["items"]
        assert released == []
        deleted = client.delete(f"/api/v1/assets/{seeded['garment']}/content", headers=headers)
        assert deleted.status_code == 200, deleted.text


def test_comfy_layer_job_requires_active_workflow(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path, adapter_type="comfyui")
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-comfy-session"},
        ).json()
        rejected = client.post(
            f"/api/v1/outfits/{created['id']}/branches/{created['branches'][0]['id']}/layers",
            json={
                "role": "inner_top",
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "candidate_count": 1,
            },
            headers={**headers, "Idempotency-Key": "ol-comfy-layer"},
        )
        assert rejected.status_code == 409
        assert rejected.json()["code"] == "workflow_not_active"


def test_add_layer_rejects_provider_without_layering(tmp_path: Path) -> None:
    client, credentials, seeded = _build(tmp_path, sequential=False)
    headers = {"Authorization": f"Bearer {credentials['app']}"}
    with client:
        created = client.post(
            "/api/v1/outfits",
            json={"person_asset_id": seeded["person"]},
            headers={**headers, "Idempotency-Key": "ol-session-0002"},
        ).json()
        rejected = client.post(
            f"/api/v1/outfits/{created['id']}/branches/{created['branches'][0]['id']}/layers",
            json={
                "role": "inner_top",
                "garment_asset_id": seeded["garment"],
                "provider_id": seeded["provider"],
                "candidate_count": 1,
            },
            headers={**headers, "Idempotency-Key": "ol-layer-0002"},
        )
        assert rejected.status_code == 409
        assert rejected.json()["code"] == "provider_not_usable"
