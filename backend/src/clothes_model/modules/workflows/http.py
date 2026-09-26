from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Workflows"])
add_stub_routes(
    router,
    (
        StubRoute("/api/v1/admin/workflows", "GET", "listWorkflowVersions"),
        StubRoute("/api/v1/admin/workflows", "POST", "createWorkflowVersion"),
        StubRoute("/api/v1/admin/workflows/{workflow_version_id}", "GET", "getWorkflowVersion"),
        StubRoute(
            "/api/v1/admin/workflows/{workflow_version_id}/validate",
            "POST",
            "validateWorkflowVersion",
        ),
        StubRoute(
            "/api/v1/admin/workflows/{workflow_version_id}/activate",
            "POST",
            "activateWorkflowVersion",
        ),
    ),
)
