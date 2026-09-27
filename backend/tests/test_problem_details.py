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

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-request-id"] == "test-request-123"
    assert response.json() == {
        "type": "https://clothes-model.local/problems/unauthorized",
        "title": "认证失败",
        "status": 401,
        "code": "unauthorized",
        "detail": "认证或授权检查失败。",
        "trace_id": "test-request-123",
        "retryable": False,
        "field_errors": [],
        "context": {},
    }


def test_unsafe_request_id_is_replaced() -> None:
    app = create_app(Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get("/api/v1/providers", headers={"X-Request-ID": "secret value"})

    assert response.status_code == 401
    assert response.headers["x-request-id"] != "secret value"
    assert response.json()["trace_id"] == response.headers["x-request-id"]
