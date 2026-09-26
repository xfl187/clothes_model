from fastapi.testclient import TestClient

from clothes_model.api.application import create_app
from clothes_model.core.config import Settings


def test_unimplemented_route_returns_safe_problem_details() -> None:
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/jobs",
            headers={"X-Request-ID": "test-request-123"},
        )

    assert response.status_code == 501
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-request-id"] == "test-request-123"
    assert response.json() == {
        "type": "https://clothes-model.local/problems/not_implemented",
        "title": "功能尚未实现",
        "status": 501,
        "code": "not_implemented",
        "detail": "该接口已建立工程契约，但业务逻辑将在后续阶段实现。",
        "trace_id": "test-request-123",
        "retryable": False,
        "field_errors": [],
        "context": {"operation_id": "listJobs"},
    }


def test_unsafe_request_id_is_replaced() -> None:
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get("/api/v1/providers", headers={"X-Request-ID": "secret value"})

    assert response.status_code == 501
    assert response.headers["x-request-id"] != "secret value"
    assert response.json()["trace_id"] == response.headers["x-request-id"]
