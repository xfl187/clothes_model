"""Process health endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from clothes_model.generated.models import HealthStatus, Status, Timestamp

router = APIRouter(tags=["Health"])


def _health(status: Status, checks: dict[str, str]) -> HealthStatus:
    return HealthStatus(
        status=status,
        checked_at=Timestamp(root=datetime.now(UTC)),
        checks=checks,
    )


@router.get("/health/live", operation_id="getLiveness", response_model=HealthStatus)
async def get_liveness() -> HealthStatus:
    return _health(Status.ok, {"process": "ok"})


@router.get("/health/ready", operation_id="getReadiness", response_model=HealthStatus)
async def get_readiness(request: Request) -> HealthStatus:
    environment: str = request.app.state.settings.environment
    scheduler_status: str = request.app.state.scheduler.status
    return _health(
        Status.ok,
        {
            "configuration": "ok",
            "environment": environment,
            "scheduler": scheduler_status,
        },
    )
