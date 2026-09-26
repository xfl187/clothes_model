from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Providers"])
add_stub_routes(
    router,
    (
        StubRoute("/api/v1/providers", "GET", "listAvailableProviders"),
        StubRoute("/api/v1/admin/provider-configs", "GET", "listProviderConfigs"),
        StubRoute("/api/v1/admin/provider-configs", "POST", "createProviderConfig"),
        StubRoute("/api/v1/admin/provider-configs/{provider_id}", "GET", "getProviderConfig"),
        StubRoute("/api/v1/admin/provider-configs/{provider_id}", "PUT", "updateProviderConfig"),
        StubRoute(
            "/api/v1/admin/provider-configs/{provider_id}/validate",
            "POST",
            "validateProviderConfig",
        ),
        StubRoute(
            "/api/v1/admin/provider-configs/{provider_id}/enable",
            "POST",
            "enableProviderConfig",
        ),
    ),
)
