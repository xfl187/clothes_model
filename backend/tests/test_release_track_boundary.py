import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.auth.application import TokenService
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
)


def _seed(database_url: str) -> tuple[dict[str, str], str, str]:
    direct_id, comfy_id = str(uuid4()), str(uuid4())

    async def run() -> dict[str, str]:
        runtime = create_database_runtime(database_url, 5000)
        try:
            tokens = {
                item.scope: item.value
                for item in await TokenService(
                    lambda: SqlAlchemyUnitOfWork(runtime.sessions)
                ).bootstrap()
            }
            now = datetime.now(UTC)
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                for provider_id, provider_type, adapter in (
                    (direct_id, "llm_image_edit", "fake_image_edit"),
                    (comfy_id, "comfyui", "comfyui"),
                ):
                    await uow.provider_configs.add_config(
                        ProviderConfig(
                            id=provider_id,
                            display_name=provider_type,
                            provider_type=provider_type,  # type: ignore[arg-type]
                            state="active",
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await uow.provider_configs.add_revision(
                        ProviderConfigRevision(
                            id=str(uuid4()),
                            provider_id=provider_id,
                            revision=1,
                            adapter_type=adapter,
                            endpoint="https://provider.invalid",
                            model="test-model",
                            timeout_seconds=30,
                            capabilities_json=ProviderCapabilities(manual_mask=True).to_json(),
                            vendor_parameters_json="{}",
                            created_at=now,
                        )
                    )
                await uow.commit()
            return tokens
        finally:
            await runtime.close()

    return asyncio.run(run()), direct_id, comfy_id


def _settings(database_url: str, tmp_path: Path, release: str) -> Settings:
    return Settings(
        environment="test",
        product_release=release,  # type: ignore[arg-type]
        database_url=database_url,
        storage_root=tmp_path / f"storage-{release}",
        instance_lock_path=tmp_path / f"instance-{release}.lock",
        admin_session_cookie_secure=False,
        scheduler_enabled=False,
    )


def _login(client: TestClient, admin_token: str) -> str:
    response = client.post("/api/v1/admin/auth/session", json={"admin_token": admin_token})
    assert response.status_code == 201
    return str(response.json()["csrf_token"])


def test_v1_hides_and_rejects_v1_1_surfaces(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'release.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    tokens, direct_id, comfy_id = _seed(database_url)

    with TestClient(create_app(_settings(database_url, tmp_path, "v1"))) as client:
        csrf = _login(client, tokens["admin"])
        app_headers = {"Authorization": f"Bearer {tokens['app']}"}
        admin_items = client.get("/api/v1/admin/provider-configs").json()["items"]
        app_items = client.get("/api/v1/providers", headers=app_headers).json()["items"]
        assert [item["id"] for item in admin_items] == [direct_id]
        assert [item["id"] for item in app_items] == [direct_id]

        blocked = [
            client.get("/api/v1/admin/configuration/comfy-node"),
            client.get("/api/v1/admin/workflows"),
            client.post(
                "/api/v1/outfits",
                json={"person_asset_id": str(uuid4())},
                headers={**app_headers, "Idempotency-Key": "release-outfit-0001"},
            ),
            client.put(
                "/api/v1/admin/configuration/default-provider",
                json={"provider_id": comfy_id, "confirm_new_jobs_only": True},
                headers={"X-CSRF-Token": csrf},
            ),
            client.post(
                "/api/v1/jobs",
                json={
                    "person_asset_ids": [str(uuid4())],
                    "garment_asset_id": str(uuid4()),
                    "provider_id": comfy_id,
                    "mode": "precise_try_on",
                    "generation_options": {"candidate_count": 1},
                },
                headers={**app_headers, "Idempotency-Key": "release-job-0001"},
            ),
        ]
        assert all(response.status_code == 404 for response in blocked), [
            (response.status_code, response.text) for response in blocked
        ]
        assert all(response.json()["code"] == "feature_not_available" for response in blocked)

        overview = client.get("/api/v1/admin/system/overview").json()
        assert "comfyui" not in [item["key"] for item in overview["dependencies"]]
        assert "active_workflow" not in overview["effective_configuration"]
        assert overview["effective_configuration"]["product_release"] == "v1"


def test_v1_1_preserves_comfyui_availability(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'release-v11.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration-v11.lock")
    tokens, direct_id, comfy_id = _seed(database_url)

    with TestClient(create_app(_settings(database_url, tmp_path, "v1_1"))) as client:
        _login(client, tokens["admin"])
        items = client.get("/api/v1/admin/provider-configs").json()["items"]
        assert {direct_id, comfy_id} <= {item["id"] for item in items}
        assert client.get("/api/v1/admin/workflows").status_code == 200
        overview = client.get("/api/v1/admin/system/overview").json()
        assert "comfyui" in [item["key"] for item in overview["dependencies"]]
        assert overview["effective_configuration"]["product_release"] == "v1_1"
