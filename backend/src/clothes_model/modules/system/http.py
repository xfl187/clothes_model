"""System overview aggregation for Web Admin."""

import shutil
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from clothes_model.core.problems import AppProblem
from clothes_model.core.features import feature_enabled, unfinished_comfy_job_count
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules.auth.http import AdminIdentity, require_admin

router = APIRouter(tags=["Admin Configuration"])

_BLOCKER_TARGET = {
    "waiting_provider": ("job", "warning"),
    "storage_blocked_queue": ("storage", "critical"),
    "needs_attention": ("job", "critical"),
    "configuration_fault": ("provider", "critical"),
}


async def _dependency_rows(request: Request) -> list[dict[str, object]]:
    dependencies: list[dict[str, object]] = [
        {"key": "business_service", "state": "ok", "detail": None}
    ]

    database_state = "ok"
    try:
        async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
            await uow.session.scalar(select(1))
    except Exception:
        database_state = "unavailable"
    dependencies.append({"key": "database", "state": database_state, "detail": None})

    storage_state = "ok"
    reserve = request.app.state.settings.storage_reserve_bytes
    try:
        usage = shutil.disk_usage(request.app.state.storage.root)
        if usage.free <= reserve:
            storage_state = "degraded"
    except Exception:
        storage_state = "unavailable"
    dependencies.append({"key": "storage", "state": storage_state, "detail": None})

    if feature_enabled(request, "comfyui"):
        comfy_state = "unknown"
        try:
            async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
                health = await uow.session.scalar(
                    select(db.comfy_node_config.c.health_status).where(
                        db.comfy_node_config.c.id == "default"
                    )
                )
            comfy_state = {
                "healthy": "ok",
                "offline": "degraded",
                "incompatible": "degraded",
                "unchecked": "unknown",
            }.get(str(health), "unknown")
        except Exception:
            comfy_state = "unavailable"
        dependencies.append({"key": "comfyui", "state": comfy_state, "detail": None})
    return dependencies


async def _blockers(request: Request) -> list[dict[str, object]]:
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        waiting = int(
            await uow.session.scalar(
                select(func.count())
                .select_from(db.job_items)
                .where(db.job_items.c.state == "waiting_provider")
            )
            or 0
        )
        storage_blocked = int(
            await uow.session.scalar(
                select(func.count())
                .select_from(db.job_items)
                .where(db.job_items.c.block_reason == "storage_capacity")
            )
            or 0
        )
        needs_attention = int(
            await uow.session.scalar(
                select(func.count())
                .select_from(db.job_items)
                .where(db.job_items.c.state == "needs_attention")
            )
            or 0
        )
        configuration_faults = int(
            await uow.session.scalar(
                select(func.count())
                .select_from(db.job_items)
                .where(
                    db.job_items.c.block_reason.in_(
                        ("configuration_invalid", "locked_configuration_unavailable")
                    )
                )
            )
            or 0
        )
    counts = {
        "waiting_provider": waiting,
        "storage_blocked_queue": storage_blocked,
        "needs_attention": needs_attention,
        "configuration_fault": configuration_faults,
    }
    blockers: list[dict[str, object]] = []
    for kind, count in counts.items():
        if count > 0:
            blockers.append({"kind": kind, "count": count, "deep_link": _deep_link(kind)})
    return blockers


def _deep_link(kind: str) -> str:
    if kind == "storage_blocked_queue":
        return "/storage"
    if kind == "configuration_fault":
        return "/providers"
    return "/diagnostics"


def _action_items(blockers: list[dict[str, object]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for blocker in blockers:
        kind = str(blocker["kind"])
        target_kind, severity = _BLOCKER_TARGET.get(kind, ("unknown", "warning"))
        items.append(
            {
                "id": f"{kind}",
                "severity": severity,
                "summary": _summary(kind, int(blocker["count"])),  # type: ignore[arg-type]
                "target_kind": target_kind,
                "target_id": None,
            }
        )
    return items


def _summary(kind: str, count: int) -> str:
    text = {
        "waiting_provider": "等待 Provider 的任务",
        "storage_blocked_queue": "因存储不足阻塞的任务",
        "needs_attention": "需要人工处理的任务",
        "configuration_fault": "配置故障阻止的任务",
    }.get(kind, "需要处理的事项")
    return f"{text}，共 {count} 项"


async def _effective_configuration(request: Request) -> dict[str, Any]:
    result: dict[str, Any] = {
        "product_release": request.app.state.settings.product_release,
        "enabled_features": list(request.app.state.settings.enabled_product_features()),
    }
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        default = (
            await uow.session.execute(
                select(
                    db.provider_default_selection.c.provider_id,
                    db.provider_default_selection.c.config_revision_id,
                    db.provider_config_revisions.c.revision,
                )
                .join(
                    db.provider_config_revisions,
                    db.provider_config_revisions.c.id
                    == db.provider_default_selection.c.config_revision_id,
                )
                .where(db.provider_default_selection.c.id == "default")
            )
        ).one_or_none()
        default_is_comfy = False
        if default is not None:
            selected_type = await uow.session.scalar(
                select(db.provider_configs.c.provider_type).where(
                    db.provider_configs.c.id == default[0]
                )
            )
            default_is_comfy = selected_type == "comfyui"
        if default is not None and not (
            default_is_comfy and not feature_enabled(request, "comfyui")
        ):
            result["default_provider"] = {
                "provider_id": default[0],
                "config_version_id": default[1],
                "revision": default[2],
            }

        active_llm = (
            await uow.session.execute(
                select(
                    db.provider_configs.c.id,
                    db.provider_config_revisions.c.id,
                    db.provider_config_revisions.c.revision,
                )
                .join(
                    db.provider_config_revisions,
                    db.provider_config_revisions.c.provider_id == db.provider_configs.c.id,
                )
                .where(
                    db.provider_configs.c.state == "active",
                    db.provider_configs.c.provider_type == "llm_image_edit",
                )
                .order_by(db.provider_config_revisions.c.revision.desc())
                .limit(1)
            )
        ).first()
        if active_llm is not None:
            result["active_llm_provider"] = {
                "provider_id": active_llm[0],
                "config_version_id": active_llm[1],
                "revision": active_llm[2],
            }

        workflow = (
            await uow.session.execute(
                select(
                    db.workflow_versions.c.workflow_id,
                    db.workflow_versions.c.id,
                    db.workflow_versions.c.version,
                    db.workflow_versions.c.workflow_sha256,
                    db.workflow_versions.c.manifest_sha256,
                )
                .where(db.workflow_versions.c.state == "active")
                .limit(1)
            )
        ).first()
        if workflow is not None and feature_enabled(request, "comfyui"):
            result["active_workflow"] = {
                "workflow_id": workflow[0],
                "workflow_version_id": workflow[1],
                "version": workflow[2],
                "workflow_sha256": workflow[3],
                "manifest_sha256": workflow[4],
            }
    return result


def _verdict(dependencies: list[dict[str, object]], blockers: list[dict[str, object]]) -> str:
    critical = any(
        _BLOCKER_TARGET.get(str(blocker["kind"]), ("", "warning"))[1] == "critical"
        for blocker in blockers
    )
    if critical:
        return "action_required"
    limited = any(dep["state"] != "ok" for dep in dependencies) or bool(blockers)
    return "limited" if limited else "ok"


@router.get("/api/v1/admin/system/overview", operation_id="getSystemOverview")
async def get_system_overview(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    try:
        dependencies = await _dependency_rows(request)
        blockers = await _blockers(request)
        if not feature_enabled(request, "comfyui"):
            unfinished = await unfinished_comfy_job_count(request)
            if unfinished:
                blockers.append(
                    {
                        "kind": "configuration_fault",
                        "count": unfinished,
                        "deep_link": "/diagnostics",
                    }
                )
        effective = await _effective_configuration(request)
    except AppProblem:
        raise
    except Exception as error:  # pragma: no cover - defensive aggregation boundary
        raise AppProblem(
            503,
            "system_overview_unavailable",
            "系统概览不可用",
            "无法聚合系统状态，请稍后重试。",
        ) from error
    return {
        "verdict": _verdict(dependencies, blockers),
        "snapshot_at": datetime.now(UTC),
        "dependencies": dependencies,
        "blockers": blockers,
        "action_items": _action_items(blockers),
        "effective_configuration": effective,
    }
