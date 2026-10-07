"""Central route registry for the modular monolith."""

from fastapi import FastAPI

from clothes_model.api.health import router as health_router
from clothes_model.modules.admin.http import router as admin_router
from clothes_model.modules.assets.http import router as assets_router
from clothes_model.modules.auth.http import router as auth_router
from clothes_model.modules.cleanup.http import router as cleanup_router
from clothes_model.modules.jobs.http import router as jobs_router
from clothes_model.modules.outfits.http import router as outfits_router
from clothes_model.modules.providers.http import router as providers_router
from clothes_model.modules.system.http import router as system_router
from clothes_model.modules.workflows.http import router as workflows_router


def register_routes(app: FastAPI) -> None:
    for router in (
        health_router,
        auth_router,
        assets_router,
        jobs_router,
        outfits_router,
        providers_router,
        workflows_router,
        system_router,
        admin_router,
        cleanup_router,
    ):
        app.include_router(router)
