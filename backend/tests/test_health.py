from datetime import datetime

from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings


def test_live_and_ready_match_contract() -> None:
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert live.json()["checks"] == {"process": "ok"}
    datetime.fromisoformat(live.json()["checked_at"].replace("Z", "+00:00"))
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    checks = ready.json()["checks"]
    assert checks["configuration"] == "ok"
    assert checks["environment"] == "test"
    assert checks["scheduler"] == "disabled"
    assert set(checks) >= {
        "comfy_node_health",
        "active_workflow",
        "waiting_provider_items",
        "storage_blocked_items",
    }
    assert live.headers["x-request-id"]
    assert ready.headers["x-request-id"]
