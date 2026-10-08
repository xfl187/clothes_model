"""Process health endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from clothes_model.core.config import Settings
from clothes_model.generated.models import (
    HealthStatus,
    ProductFeature,
    ProductRelease,
    Status,
    Timestamp,
)
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db

router = APIRouter(tags=["Health"])


def _health(status: Status, checks: dict[str, str], settings: Settings) -> HealthStatus:
    return HealthStatus(
        status=status,
        checked_at=Timestamp(root=datetime.now(UTC)),
        product_release=ProductRelease(settings.product_release),
        enabled_features=[
            ProductFeature(feature) for feature in settings.enabled_product_features()
        ],
        checks=checks,
    )


async def _comfy_diagnostics(request: Request) -> dict[str, str]:
    """Redacted Comfy/Workflow conclusions without endpoints, secrets, or bodies."""

    diagnostics = {
        "comfy_node_health": "unknown",
        "active_workflow": "unknown",
        "waiting_provider_items": "0",
        "storage_blocked_items": "0",
    }
    try:
        async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
            node_health = await uow.session.scalar(
                select(db.comfy_node_config.c.health_status).where(
                    db.comfy_node_config.c.id == "default"
                )
            )
            active = (
                await uow.session.execute(
                    select(
                        db.workflow_versions.c.workflow_id,
                        db.workflow_versions.c.version,
                    ).where(
                        db.workflow_versions.c.mode == "precise_try_on",
                        db.workflow_versions.c.state == "active",
                    )
                )
            ).one_or_none()
            waiting = await uow.session.scalar(
                select(func.count())
                .select_from(db.job_items)
                .where(db.job_items.c.state == "waiting_provider")
            )
            blocked = await uow.session.scalar(
                select(func.count())
                .select_from(db.job_items)
                .where(db.job_items.c.block_reason == "storage_capacity")
            )
    except Exception:
        diagnostics["comfy_node_health"] = "unavailable"
        return diagnostics
    diagnostics["comfy_node_health"] = str(node_health or "unconfigured")
    diagnostics["active_workflow"] = (
        f"{active[0]}:{active[1]}" if active is not None else "none"
    )
    diagnostics["waiting_provider_items"] = str(waiting or 0)
    diagnostics["storage_blocked_items"] = str(blocked or 0)
    return diagnostics


@router.get("/health/live", operation_id="getLiveness", response_model=HealthStatus)
async def get_liveness(request: Request) -> HealthStatus:
    return _health(Status.ok, {"process": "ok"}, request.app.state.settings)


@router.get("/health/ready", operation_id="getReadiness", response_model=HealthStatus)
async def get_readiness(request: Request) -> HealthStatus:
    environment: str = request.app.state.settings.environment
    scheduler_status: str = request.app.state.scheduler.status
    checks = {
        "configuration": "ok",
        "environment": environment,
        "scheduler": scheduler_status,
    }
    checks.update(await _comfy_diagnostics(request))
    return _health(Status.ok, checks, request.app.state.settings)
