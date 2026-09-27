"""Durable job creation and authoritative job/item query HTTP API."""

import base64
import hashlib
import json
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select

from clothes_model.core.problems import AppProblem
from clothes_model.generated.models import CreateJobRequest
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules._stub import StubRoute, add_stub_routes
from clothes_model.modules.assets.domain import AssetReference, IdempotencyRecord
from clothes_model.modules.auth.application import VerifiedCredential
from clothes_model.modules.auth.http import require_app
from clothes_model.modules.jobs.domain import Job, JobItem, JobPersonInput
from clothes_model.modules.jobs.payloads import item_payload, job_payload
from clothes_model.modules.providers.application.services import ProviderConfigService

router = APIRouter(tags=["Jobs"])
AppIdentity = Annotated[VerifiedCredential, Depends(require_app)]


def _problem(status: int, code: str, detail: str, *, retryable: bool = False) -> AppProblem:
    return AppProblem(status, code, "任务请求无法完成", detail, retryable=retryable)


def _as_mapping(value: object) -> Mapping[str, object]:
    return cast(Mapping[str, object], value) if isinstance(value, dict) else {}


def _as_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _provider_service(request: Request) -> ProviderConfigService:
    return ProviderConfigService(
        lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions),
        request.app.state.provider_registry,
        request.app.state.secret_cipher,
    )


def _ensure_capacity(request: Request) -> None:
    usage = shutil.disk_usage(request.app.state.storage.root)
    if usage.free - request.app.state.settings.storage_reserve_bytes <= 0:
        raise _problem(
            507,
            "storage_capacity",
            "存储空间不足，暂时不能创建任务。",
            retryable=True,
        )


def _cursor(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "===").decode())
        return str(decoded[0]), str(decoded[1])
    except Exception as error:
        raise _problem(422, "validation_error", "游标无效。") from error


def _encode_cursor(created_at: datetime, job_id: str) -> str:
    raw = json.dumps([created_at.isoformat(), job_id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


async def _asset_available(
    uow: SqlAlchemyUnitOfWork, asset_id: str, kind: str
) -> bool:
    found = await uow.session.scalar(
        select(db.assets.c.id).where(
            db.assets.c.id == asset_id,
            db.assets.c.kind == kind,
            db.assets.c.content_state == "available",
        )
    )
    return found is not None


@router.get("/api/v1/jobs", operation_id="listJobs")
async def list_jobs(
    request: Request,
    identity: AppIdentity,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    state: str | None = None,
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        jobs = await uow.jobs.list_jobs(state=state, limit=limit + 1)
        decoded = _cursor(cursor)
        if decoded:
            created, job_id = decoded
            boundary = datetime.fromisoformat(created)
            jobs = [
                job
                for job in jobs
                if (job.created_at, job.id) < (boundary, job_id)
            ]
        page = jobs[:limit]
        items = [await job_payload(uow, job) for job in page]
        has_more = len(jobs) > limit
        next_cursor = (
            _encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
        )
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


@router.post("/api/v1/jobs", status_code=201, operation_id="createJob")
async def create_job(
    request: Request,
    body: CreateJobRequest,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    if body.mode.value != "precise_try_on":
        raise _problem(422, "validation_error", "Phase 3 仅支持精准换装模式。")
    if body.mask_asset_id is not None:
        raise _problem(422, "validation_error", "Phase 3 尚不支持遮罩素材。")
    request_digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    provider_id = str(body.provider_id.root)
    garment_asset_id = str(body.garment_asset_id.root)
    person_asset_ids = [str(asset.root) for asset in body.person_asset_ids]
    candidate_count = body.generation_options.candidate_count

    service = _provider_service(request)
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        existing = await uow.idempotency.get_bound(
            "app", identity.token_id, "job.create", key_digest
        )
        if existing is not None:
            if existing.request_digest != request_digest:
                raise _problem(409, "idempotency_key_reused", "幂等键已绑定到不同请求。")
            job = await uow.jobs.get_job(str(existing.resource_id))
            if job is None:
                raise _problem(409, "idempotency_result_missing", "幂等结果不可用。")
            return await job_payload(uow, job)

        config = await service.get(provider_id)
        revision = await service.current_revision(provider_id)
        if config is None or revision is None:
            raise _problem(409, "provider_not_usable", "所选 Provider 不存在。")
        if config.state not in {"active", "validated"}:
            raise _problem(409, "provider_not_usable", "所选 Provider 未启用。")
        capabilities = _as_mapping(json.loads(revision.capabilities_json or "{}"))
        max_candidates = _as_int(
            _as_mapping(capabilities.get("output_constraints")).get("max_candidates"), 4
        )
        if candidate_count > max_candidates:
            raise _problem(409, "provider_not_usable", "所选 Provider 不支持该候选数量。")

        checks = [(garment_asset_id, "garment"), *((pid, "person") for pid in person_asset_ids)]
        for asset_id, kind in checks:
            if not await _asset_available(uow, asset_id, kind):
                raise _problem(422, "validation_error", "输入素材不存在或不可用。")
        if body.related_job_id is not None:
            related = await uow.jobs.get_job(str(body.related_job_id))
            if related is None:
                raise _problem(422, "validation_error", "关联任务不存在。")

        _ensure_capacity(request)

        availability = await service.availability_for(config, revision)
        waiting = availability == "temporarily_offline"
        now = datetime.now(UTC)
        job_id = str(uuid4())
        snapshot = {
            "label": f"{config.display_name} · {revision.model}",
            "adapter_type": revision.adapter_type,
            "model": revision.model,
            "semantic_parameters": json.loads(revision.vendor_parameters_json or "{}"),
            "capabilities_schema_version": 1,
            "capabilities": json.loads(revision.capabilities_json),
        }
        job = Job(
            id=job_id,
            mode="precise_try_on",
            state="waiting_provider" if waiting else "queued",
            candidate_count=candidate_count,
            garment_asset_id=garment_asset_id,
            provider_id=provider_id,
            provider_revision_id=revision.id,
            provider_snapshot_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
            block_reason="provider_offline" if waiting else None,
            blocked_detail="Provider 暂时离线，恢复后任务会自动继续。" if waiting else None,
            seed=body.generation_options.seed,
            advanced_parameters_json=json.dumps(
                body.generation_options.advanced_parameters or {},
                separators=(",", ":"),
                sort_keys=True,
            ),
            related_job_id=str(body.related_job_id) if body.related_job_id else None,
            created_at=now,
            updated_at=now,
        )
        await uow.jobs.add_job(job)
        for ordinal, asset_id in enumerate(person_asset_ids):
            await uow.jobs.add_person_input(
                JobPersonInput(
                    job_id=job_id,
                    person_asset_id=asset_id,
                    ordinal=ordinal,
                    created_at=now,
                )
            )
        for candidate_index in range(candidate_count):
            await uow.jobs.add_item(
                JobItem(
                    id=str(uuid4()),
                    job_id=job_id,
                    person_asset_id=person_asset_ids[0],
                    candidate_index=candidate_index,
                    attempt=1,
                    state="waiting_provider" if waiting else "queued",
                    block_reason="provider_offline" if waiting else None,
                    created_at=now,
                    updated_at=now,
                )
            )
        reference_ids = [garment_asset_id, *person_asset_ids]
        for asset_id in reference_ids:
            await uow.asset_references.add(
                AssetReference(
                    id=str(uuid4()),
                    asset_id=asset_id,
                    source_kind="job",
                    source_id=job_id,
                    active=True,
                    created_at=now,
                    display_label="试穿任务",
                )
            )
        await uow.idempotency.add(
            IdempotencyRecord(
                id=str(uuid4()),
                actor_scope="app",
                actor_id=identity.token_id,
                operation="job.create",
                key_digest=key_digest,
                request_digest=request_digest,
                state="completed",
                response_status=201,
                resource_id=job_id,
                created_at=now,
                expires_at=now + timedelta(days=1),
            )
        )
        await uow.commit()
        return await job_payload(uow, job)


@router.get("/api/v1/jobs/{job_id}", operation_id="getJob")
async def get_job(request: Request, job_id: str, identity: AppIdentity) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        job = await uow.jobs.get_job(job_id)
        if job is None:
            raise _problem(404, "not_found", "任务不存在。")
        return await job_payload(uow, job)


@router.get("/api/v1/job-items/{job_item_id}", operation_id="getJobItem")
async def get_job_item(
    request: Request, job_item_id: str, identity: AppIdentity
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        item = await uow.jobs.get_item(job_item_id)
        if item is None:
            raise _problem(404, "not_found", "候选任务不存在。")
        return await item_payload(uow, item)


add_stub_routes(
    router,
    (
        StubRoute("/api/v1/jobs/{job_id}/cancel", "POST", "cancelJob"),
        StubRoute("/api/v1/job-items/{job_item_id}/cancel", "POST", "cancelJobItem"),
        StubRoute("/api/v1/job-items/{job_item_id}/retry", "POST", "retryJobItem"),
        StubRoute("/api/v1/job-items/{job_item_id}/requery", "POST", "requeryJobItem"),
        StubRoute(
            "/api/v1/job-items/{job_item_id}/finish-failed",
            "POST",
            "finishJobItemAsFailed",
        ),
    ),
)
