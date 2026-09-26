from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Admin", "Diagnostics"])
add_stub_routes(
    router,
    (
        StubRoute(
            "/api/v1/admin/configuration/default-provider",
            "GET",
            "getDefaultProviderConfiguration",
        ),
        StubRoute(
            "/api/v1/admin/configuration/default-provider",
            "PUT",
            "updateDefaultProviderConfiguration",
        ),
        StubRoute("/api/v1/admin/configuration/comfy-node", "GET", "getComfyNodeConfiguration"),
        StubRoute("/api/v1/admin/configuration/comfy-node", "PUT", "updateComfyNodeConfiguration"),
        StubRoute(
            "/api/v1/admin/configuration/comfy-node/test",
            "POST",
            "testComfyNodeConnection",
        ),
        StubRoute("/api/v1/admin/configuration/retention", "GET", "getRetentionPolicy"),
        StubRoute("/api/v1/admin/configuration/retention", "PUT", "updateRetentionPolicy"),
        StubRoute("/api/v1/admin/storage", "GET", "getStorageStatus"),
        StubRoute("/api/v1/admin/storage/scan", "POST", "scanStorage"),
        StubRoute("/api/v1/admin/diagnostics/jobs", "GET", "listDiagnosticJobs"),
        StubRoute("/api/v1/admin/diagnostics/jobs/{job_id}", "GET", "getDiagnosticJob"),
    ),
)
