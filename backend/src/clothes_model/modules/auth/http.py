from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Authentication"])
add_stub_routes(
    router,
    (
        StubRoute("/api/v1/auth/status", "GET", "getAppAuthStatus"),
        StubRoute("/api/v1/admin/auth/session", "GET", "getAdminSession"),
        StubRoute("/api/v1/admin/auth/session", "POST", "createAdminSession"),
        StubRoute("/api/v1/admin/auth/session", "DELETE", "deleteAdminSession"),
    ),
)
