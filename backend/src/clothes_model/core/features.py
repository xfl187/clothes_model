"""Server-authoritative product feature gates."""

from typing import Literal

from fastapi import Request
from sqlalchemy import func, or_, select

from clothes_model.core.problems import AppProblem
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db

ProductFeatureName = Literal["direct_model_try_on", "comfyui", "layered_outfits"]


def feature_enabled(request: Request, feature: ProductFeatureName) -> bool:
    return feature in request.app.state.settings.enabled_product_features()


def require_feature(request: Request, feature: ProductFeatureName) -> None:
    if feature_enabled(request, feature):
        return
    raise AppProblem(
        404,
        "feature_not_available",
        "功能在当前版本不可用",
        "该功能未在当前产品版本中启用。",
        context={
            "feature": feature,
            "product_release": request.app.state.settings.product_release,
        },
    )


async def unfinished_comfy_job_count(request: Request) -> int:
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        count = await uow.session.scalar(
            select(func.count())
            .select_from(db.jobs)
            .join(db.provider_configs, db.provider_configs.c.id == db.jobs.c.provider_id)
            .where(
                db.jobs.c.state.not_in(("succeeded", "partially_succeeded", "failed", "cancelled")),
                or_(
                    db.provider_configs.c.provider_type == "comfyui",
                    db.jobs.c.workflow_version_id.is_not(None),
                ),
            )
        )
    return int(count or 0)
