"""Resumable upload and private asset HTTP API."""

import asyncio
import base64
import hashlib
import json
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import RowMapping

from clothes_model.core.problems import AppProblem
from clothes_model.generated.models import (
    AssetUpdateRequest,
    UploadCompleteRequest,
    UploadCreateRequest,
)
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.infrastructure.storage import StorageError
from clothes_model.modules.auth.application import VerifiedCredential
from clothes_model.modules.auth.http import require_app

router = APIRouter(tags=["Assets", "Uploads"])
AppIdentity = Annotated[VerifiedCredential, Depends(require_app)]
_locks: dict[str, asyncio.Lock] = {}
_TERMINAL_JOB_STATES = ("succeeded", "partially_succeeded", "failed", "cancelled")


def _problem(
    status: int,
    code: str,
    detail: str,
    *,
    context: dict[str, object] | None = None,
) -> AppProblem:
    return AppProblem(
        status,
        code,
        "请求无法完成",
        detail,
        retryable=status in {429, 507},
        context=context or {},
    )


def _upload_dict(row: Mapping[Any, Any]) -> dict[str, object]:
    data = {str(key): value for key, value in row.items()}
    return {
        "id": data["id"],
        "state": data["state"],
        "asset_kind": data["asset_kind"],
        "filename": data["filename"],
        "content_type": data["content_type"],
        "size_bytes": data["expected_size"],
        "uploaded_bytes": data["confirmed_offset"],
        "asset_id": data.get("completed_asset_id"),
        "created_at": data["created_at"],
        "expires_at": data["expires_at"],
        "error": None,
    }


async def _asset_dict(uow: SqlAlchemyUnitOfWork, asset_id: str) -> dict[str, object] | None:
    joined = db.assets.outerjoin(
        db.stored_objects, db.assets.c.stored_object_id == db.stored_objects.c.id
    ).outerjoin(db.garment_assets, db.assets.c.id == db.garment_assets.c.asset_id)
    row = (
        (
            await uow.session.execute(
                select(
                    db.assets,
                    db.stored_objects.c.content_type,
                    db.stored_objects.c.size_bytes,
                    db.stored_objects.c.width,
                    db.stored_objects.c.height,
                    db.garment_assets.c.category,
                    db.garment_assets.c.source,
                )
                .select_from(joined)
                .where(db.assets.c.id == asset_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "kind": row["kind"],
        "content_type": row["content_type"] or "application/octet-stream",
        "size_bytes": row["size_bytes"] or 0,
        "width": row["width"] or 1,
        "height": row["height"] or 1,
        "favorite": row["favorite"],
        "lifecycle": "active" if row["content_state"] == "available" else "deleted_content",
        "created_at": row["created_at"],
        "content_available": row["content_state"] == "available",
        "quality_warnings": [],
        "garment_category": row["category"],
        "garment_source": row["source"],
    }


async def _reference_source_state(
    uow: SqlAlchemyUnitOfWork, source_kind: str, source_id: str
) -> str | None:
    if source_kind == "job":
        return await uow.session.scalar(select(db.jobs.c.state).where(db.jobs.c.id == source_id))
    if source_kind in {"job_item", "generated_output"}:
        return await uow.session.scalar(
            select(db.job_items.c.state).where(db.job_items.c.id == source_id)
        )
    return None


async def _blocking_references(uow: SqlAlchemyUnitOfWork, asset_id: str) -> list[RowMapping]:
    rows = (
        (
            await uow.session.execute(
                select(db.asset_references)
                .where(
                    db.asset_references.c.asset_id == asset_id,
                    db.asset_references.c.active.is_(True),
                )
                .order_by(db.asset_references.c.created_at, db.asset_references.c.id)
            )
        )
        .mappings()
        .all()
    )
    blocking: list[RowMapping] = []
    for row in rows:
        state = await _reference_source_state(uow, row["source_kind"], row["source_id"])
        if state is None or state not in _TERMINAL_JOB_STATES:
            blocking.append(row)
    return blocking


def _temp(request: Request, name: str) -> Path:
    path = request.app.state.storage.temp / name
    if path.parent.resolve() != request.app.state.storage.temp.resolve():
        raise _problem(400, "invalid_path", "上传路径无效。")
    return path


def _capacity(request: Request, required: int) -> None:
    settings = request.app.state.settings
    free = shutil.disk_usage(request.app.state.storage.root).free
    if (
        required > settings.storage_max_upload_bytes
        or free - required < settings.storage_reserve_bytes
    ):
        raise _problem(507, "storage_capacity_blocked", "存储空间不足，当前操作已安全拒绝。")


@router.post("/api/v1/uploads", status_code=201, operation_id="createUploadSession")
async def create_upload(
    request: Request,
    body: UploadCreateRequest,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    kind = body.asset_kind.value
    if kind not in {"person", "garment", "mask"}:
        raise _problem(422, "validation_error", "当前上传类型不受支持。")
    has_category = body.garment_category is not None
    has_source = body.garment_source is not None
    if kind == "garment" and not (has_category and has_source):
        raise _problem(422, "validation_error", "衣物素材必须提供类别和来源。")
    if kind != "garment" and (has_category or has_source):
        raise _problem(422, "validation_error", "非衣物素材不能包含衣物元数据。")
    _capacity(request, body.size_bytes)
    request_digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    now, upload_id = datetime.now(UTC), str(uuid4())
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        existing = await uow.idempotency.get_bound(
            "app", identity.token_id, "upload.create", key_digest
        )
        if existing:
            if existing.request_digest != request_digest:
                raise _problem(409, "idempotency_key_reused", "幂等键已绑定到不同请求。")
            row = (
                (
                    await uow.session.execute(
                        select(db.upload_sessions).where(
                            db.upload_sessions.c.id == existing.resource_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            return _upload_dict(row)
        temp_name = f"{upload_id}.part"
        _temp(request, temp_name).touch(exist_ok=False)
        values = {
            "id": upload_id,
            "actor_token_id": identity.token_id,
            "asset_kind": kind,
            "filename": body.filename,
            "content_type": body.content_type,
            "expected_size": body.size_bytes,
            "confirmed_offset": 0,
            "temp_name": temp_name,
            "state": "created",
            "garment_category": body.garment_category.value if body.garment_category else None,
            "garment_source": body.garment_source.value if body.garment_source else None,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(hours=24),
        }
        await uow.session.execute(insert(db.upload_sessions).values(**values))
        await uow.session.execute(
            insert(db.idempotency_records).values(
                id=str(uuid4()),
                actor_scope="app",
                actor_id=identity.token_id,
                operation="upload.create",
                key_digest=key_digest,
                request_digest=request_digest,
                state="completed",
                response_status=201,
                resource_id=upload_id,
                created_at=now,
                expires_at=now + timedelta(days=1),
            )
        )
        await uow.commit()
        return _upload_dict(values)


async def _owned_upload(
    request: Request, upload_id: str, identity: VerifiedCredential
) -> tuple[SqlAlchemyUnitOfWork, RowMapping]:
    uow = SqlAlchemyUnitOfWork(request.app.state.database.sessions)
    await uow.__aenter__()
    row = (
        (
            await uow.session.execute(
                select(db.upload_sessions).where(
                    db.upload_sessions.c.id == upload_id,
                    db.upload_sessions.c.actor_token_id == identity.token_id,
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        await uow.__aexit__(None, None, None)
        raise _problem(404, "not_found", "上传不存在。")
    path = _temp(request, row["temp_name"])
    if path.exists() and path.stat().st_size > row["confirmed_offset"]:
        with path.open("r+b") as handle:
            handle.truncate(row["confirmed_offset"])
    return uow, row


@router.get("/api/v1/uploads/{upload_id}", operation_id="getUploadSession")
async def get_upload(request: Request, upload_id: str, identity: AppIdentity) -> dict[str, object]:
    uow, row = await _owned_upload(request, upload_id, identity)
    try:
        return _upload_dict(row)
    finally:
        await uow.__aexit__(None, None, None)


@router.patch("/api/v1/uploads/{upload_id}/content", operation_id="appendUploadContent")
async def append_upload(
    request: Request,
    upload_id: str,
    identity: AppIdentity,
    upload_offset: int = Header(alias="Upload-Offset"),
) -> dict[str, object]:
    content = await request.body()
    _capacity(request, len(content))
    async with _locks.setdefault(upload_id, asyncio.Lock()):
        uow, row = await _owned_upload(request, upload_id, identity)
        try:
            if (
                row["state"] not in {"created", "uploading"}
                or upload_offset != row["confirmed_offset"]
            ):
                raise _problem(409, "upload_offset_conflict", "上传偏移或状态不匹配。")
            new_offset = upload_offset + len(content)
            if new_offset > row["expected_size"]:
                raise _problem(422, "validation_error", "上传内容超过声明大小。")
            with _temp(request, row["temp_name"]).open("ab") as handle:
                handle.write(content)
                handle.flush()
            await uow.session.execute(
                update(db.upload_sessions)
                .where(db.upload_sessions.c.id == upload_id)
                .values(
                    confirmed_offset=new_offset, state="uploading", updated_at=datetime.now(UTC)
                )
            )
            await uow.commit()
            return {"upload_id": upload_id, "state": "uploading", "uploaded_bytes": new_offset}
        finally:
            await uow.__aexit__(None, None, None)


@router.delete("/api/v1/uploads/{upload_id}", operation_id="cancelUploadSession")
async def cancel_upload(
    request: Request, upload_id: str, identity: AppIdentity
) -> dict[str, object]:
    uow, row = await _owned_upload(request, upload_id, identity)
    try:
        if row["state"] not in {"completed", "cancelled"}:
            await uow.session.execute(
                update(db.upload_sessions)
                .where(db.upload_sessions.c.id == upload_id)
                .values(state="cancelled", updated_at=datetime.now(UTC))
            )
            await uow.commit()
            _temp(request, row["temp_name"]).unlink(missing_ok=True)
            row = {**dict(row), "state": "cancelled"}
        return _upload_dict(row)
    finally:
        await uow.__aexit__(None, None, None)


@router.post(
    "/api/v1/uploads/{upload_id}/complete", status_code=201, operation_id="completeUploadSession"
)
async def complete_upload(
    request: Request,
    upload_id: str,
    body: UploadCompleteRequest,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    request_digest = hashlib.sha256(f"{upload_id}:{body.model_dump_json()}".encode()).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    uow, row = await _owned_upload(request, upload_id, identity)
    try:
        existing = await uow.idempotency.get_bound(
            "app", identity.token_id, "upload.complete", key_digest
        )
        if existing:
            if existing.request_digest != request_digest:
                raise _problem(409, "idempotency_key_reused", "幂等键已绑定到不同请求。")
            if existing.resource_id is None:
                raise _problem(409, "idempotency_result_missing", "幂等结果不可用。")
            result = await _asset_dict(uow, existing.resource_id)
            if result is None:
                raise _problem(409, "idempotency_result_missing", "幂等结果不可用。")
            return result
        if row["state"] == "completed":
            result = await _asset_dict(uow, row["completed_asset_id"])
            assert result is not None
            now = datetime.now(UTC)
            await uow.session.execute(
                insert(db.idempotency_records).values(
                    id=str(uuid4()),
                    actor_scope="app",
                    actor_id=identity.token_id,
                    operation="upload.complete",
                    key_digest=key_digest,
                    request_digest=request_digest,
                    state="completed",
                    response_status=201,
                    resource_id=row["completed_asset_id"],
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
            await uow.commit()
            return result
        path = _temp(request, row["temp_name"])
        raw = path.read_bytes()
        if (
            len(raw) != row["expected_size"]
            or hashlib.sha256(raw).hexdigest().lower() != body.sha256.lower()
        ):
            raise _problem(422, "invalid_image", "大小或校验和不匹配。")
        try:
            normalized = request.app.state.storage.normalize_and_store(raw)
        except StorageError as error:
            raise _problem(422, "invalid_image", "图片无效。") from error
        object_row = (
            (
                await uow.session.execute(
                    select(db.stored_objects).where(db.stored_objects.c.sha256 == normalized.sha256)
                )
            )
            .mappings()
            .one_or_none()
        )
        object_id = object_row["id"] if object_row else str(uuid4())
        now = datetime.now(UTC)
        asset_id = str(uuid4())
        if object_row is None:
            await uow.session.execute(
                insert(db.stored_objects).values(
                    id=object_id,
                    sha256=normalized.sha256,
                    relative_path=normalized.relative_path,
                    content_type=normalized.content_type,
                    size_bytes=normalized.size_bytes,
                    width=normalized.width,
                    height=normalized.height,
                    state="available",
                    asset_ref_count=0,
                    created_at=now,
                    verified_at=now,
                )
            )
        await uow.session.execute(
            insert(db.assets).values(
                id=asset_id,
                kind=row["asset_kind"],
                stored_object_id=object_id,
                favorite=False,
                content_state="available",
                created_at=now,
                updated_at=now,
            )
        )
        if row["asset_kind"] == "person":
            await uow.session.execute(insert(db.person_assets).values(asset_id=asset_id))
        elif row["asset_kind"] == "garment":
            await uow.session.execute(
                insert(db.garment_assets).values(
                    asset_id=asset_id,
                    category=row["garment_category"],
                    source=row["garment_source"],
                )
            )
        await uow.session.execute(
            update(db.upload_sessions)
            .where(db.upload_sessions.c.id == upload_id)
            .values(state="completed", completed_asset_id=asset_id, updated_at=now)
        )
        await uow.session.execute(
            insert(db.idempotency_records).values(
                id=str(uuid4()),
                actor_scope="app",
                actor_id=identity.token_id,
                operation="upload.complete",
                key_digest=key_digest,
                request_digest=request_digest,
                state="completed",
                response_status=201,
                resource_id=asset_id,
                created_at=now,
                expires_at=now + timedelta(days=1),
            )
        )
        await uow.commit()
        path.unlink(missing_ok=True)
        result = await _asset_dict(uow, asset_id)
        assert result is not None
        return result
    finally:
        await uow.__aexit__(None, None, None)


def _cursor(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "===").decode())
        return decoded[0], decoded[1]
    except Exception as error:
        raise _problem(422, "validation_error", "游标无效。") from error


@router.get("/api/v1/assets", operation_id="listAssets")
async def list_assets(
    request: Request,
    identity: AppIdentity,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    kind: str | None = None,
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        statement = (
            select(db.assets)
            .order_by(db.assets.c.created_at.desc(), db.assets.c.id.desc())
            .limit(limit + 1)
        )
        if kind:
            statement = statement.where(db.assets.c.kind == kind)
        decoded = _cursor(cursor)
        if decoded:
            created, asset_id = decoded
            statement = statement.where(
                (db.assets.c.created_at < datetime.fromisoformat(created))
                | (
                    (db.assets.c.created_at == datetime.fromisoformat(created))
                    & (db.assets.c.id < asset_id)
                )
            )
        rows = (await uow.session.execute(statement)).mappings().all()
        page = rows[:limit]
        items = [await _asset_dict(uow, row["id"]) for row in page]
        next_cursor = ""
        if len(rows) > limit and page:
            next_cursor = (
                base64.urlsafe_b64encode(
                    json.dumps([page[-1]["created_at"].isoformat(), page[-1]["id"]]).encode()
                )
                .decode()
                .rstrip("=")
            )
        return {"items": items, "next_cursor": next_cursor, "has_more": len(rows) > limit}


@router.get("/api/v1/assets/{asset_id}", operation_id="getAsset")
async def get_asset(request: Request, asset_id: str, identity: AppIdentity) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        result = await _asset_dict(uow, asset_id)
        if result is None:
            raise _problem(404, "not_found", "素材不存在。")
        return result


@router.patch("/api/v1/assets/{asset_id}", operation_id="updateAsset")
async def update_asset(
    request: Request, asset_id: str, body: AssetUpdateRequest, identity: AppIdentity
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        await uow.session.execute(
            update(db.assets)
            .where(db.assets.c.id == asset_id)
            .values(favorite=body.favorite, updated_at=datetime.now(UTC))
        )
        await uow.commit()
        result = await _asset_dict(uow, asset_id)
        if result is None:
            raise _problem(404, "not_found", "素材不存在。")
        return result


@router.get("/api/v1/assets/{asset_id}/content", operation_id="downloadAssetContent")
async def content(request: Request, asset_id: str, identity: AppIdentity) -> FileResponse:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        row = (
            (
                await uow.session.execute(
                    select(db.stored_objects)
                    .select_from(db.assets.join(db.stored_objects))
                    .where(db.assets.c.id == asset_id, db.assets.c.content_state == "available")
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise _problem(404, "not_found", "素材内容不存在。")
        path = request.app.state.storage._confined(Path(row["relative_path"]))
        return FileResponse(
            path,
            media_type=row["content_type"],
            filename=f"{asset_id}.jpg",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )


@router.get("/api/v1/assets/{asset_id}/references", operation_id="listAssetReferences")
async def references(request: Request, asset_id: str, identity: AppIdentity) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        rows = await _blocking_references(uow, asset_id)
        return {
            "items": [
                {
                    "id": row["id"],
                    "asset_id": row["asset_id"],
                    "source_kind": row["source_kind"]
                    if row["source_kind"] in {"job", "job_item", "outfit", "generated_output"}
                    else "unknown",
                    "source_id": row["source_id"],
                    "label": row["display_label"],
                    "active": True,
                    "created_at": row["created_at"],
                }
                for row in rows
            ],
            "next_cursor": "",
            "has_more": False,
        }


@router.delete("/api/v1/assets/{asset_id}/content", operation_id="deleteAssetContent")
async def delete_content(
    request: Request, asset_id: str, identity: AppIdentity
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        blockers = await _blocking_references(uow, asset_id)
        if blockers:
            raise _problem(
                409,
                "asset_referenced",
                "素材仍被引用，不能删除内容。",
                context={"reference_count": len(blockers)},
            )
        asset = (
            (await uow.session.execute(select(db.assets).where(db.assets.c.id == asset_id)))
            .mappings()
            .one_or_none()
        )
        if asset is None:
            raise _problem(404, "not_found", "素材不存在。")
        outcome = "already_deleted"
        if asset["content_state"] == "available":
            object_id = asset["stored_object_id"]
            now = datetime.now(UTC)
            await uow.session.execute(
                update(db.assets)
                .where(db.assets.c.id == asset_id)
                .values(
                    stored_object_id=None, content_state="deleted", deleted_at=now, updated_at=now
                )
            )
            await uow.commit()
            outcome = "content_deleted"
            stored = (
                (
                    await uow.session.execute(
                        select(db.stored_objects).where(db.stored_objects.c.id == object_id)
                    )
                )
                .mappings()
                .one()
            )
            if stored["asset_ref_count"] == 0:
                request.app.state.storage.delete(stored["relative_path"])
                await uow.session.execute(
                    delete(db.stored_objects).where(db.stored_objects.c.id == object_id)
                )
                await uow.commit()
        result = await _asset_dict(uow, asset_id)
        assert result is not None
        return {"outcome": outcome, "asset": result}
