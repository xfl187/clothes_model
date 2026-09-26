from fastapi import APIRouter

from clothes_model.modules._stub import StubRoute, add_stub_routes

router = APIRouter(tags=["Storage"])
add_stub_routes(
    router,
    (StubRoute("/api/v1/admin/storage/cleanup", "POST", "cleanupStorage"),),
)
