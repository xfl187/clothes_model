from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings


def _settings(
    tmp_path: Path, *, product_release: Literal["v1", "v1_1"] = "v1"
) -> Settings:
    return Settings(
        environment="test",
        product_release=product_release,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'health.db').as_posix()}",
        storage_root=tmp_path / "storage",
        scheduler_enabled=False,
        instance_lock_path=tmp_path / "instance.lock",
    )


def test_live_and_ready_match_contract(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert live.json()["product_release"] == "v1"
    assert live.json()["enabled_features"] == ["direct_model_try_on"]
    assert live.json()["checks"] == {"process": "ok"}
    datetime.fromisoformat(live.json()["checked_at"].replace("Z", "+00:00"))
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    assert ready.json()["product_release"] == "v1"
    assert ready.json()["enabled_features"] == ["direct_model_try_on"]
    checks = ready.json()["checks"]
    assert checks["configuration"] == "ok"
    assert checks["environment"] == "test"
    assert checks["scheduler"] == "disabled"
    assert set(checks) >= {
        "waiting_provider_items",
        "storage_blocked_items",
        "release_downgrade",
    }
    assert "comfy_node_health" not in checks
    assert "active_workflow" not in checks
    assert live.headers["x-request-id"]
    assert ready.headers["x-request-id"]


def test_v1_1_health_advertises_comfyui_and_layered_outfits(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path, product_release="v1_1"))

    with TestClient(app) as client:
        body = client.get("/health/live").json()

    assert body["product_release"] == "v1_1"
    assert body["enabled_features"] == [
        "direct_model_try_on",
        "comfyui",
        "layered_outfits",
    ]
