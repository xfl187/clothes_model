"""HTTP authentication boundaries for App and Admin callers."""

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from clothes_model.core.problems import AppProblem
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules.assets.domain import IdempotencyRecord
from clothes_model.modules.auth.application.services import TokenService, VerifiedCredential
from clothes_model.modules.auth.application.sessions import AdminSessionService, digest

COOKIE_NAME = "cm_admin_session"


class AdminLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    admin_token: str = Field(min_length=32)


@dataclass(frozen=True, slots=True)
class AdminIdentity:
    session_id: str
    token_id: str


def _token_service(request: Request) -> TokenService:
    sessions = request.app.state.database.sessions
    return TokenService(lambda: SqlAlchemyUnitOfWork(sessions))


def _session_service(request: Request) -> AdminSessionService:
    settings, sessions = request.app.state.settings, request.app.state.database.sessions

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(sessions)

    return AdminSessionService(
        factory,
        TokenService(factory),
        ttl_minutes=settings.admin_session_ttl_minutes,
        max_failures=settings.admin_login_max_failures,
        window_seconds=settings.admin_login_window_seconds,
    )


def _problem(status: int, code: str) -> AppProblem:
    titles = {401: "认证失败", 403: "访问被拒绝", 429: "请求过于频繁"}
    return AppProblem(status, code, titles[status], "认证或授权检查失败。", retryable=status == 429)


def _validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/"), *request.app.state.settings.cors_allowlist}
    if origin is not None and origin.rstrip("/") not in allowed:
        raise _problem(403, "csrf_rejected")


async def require_app(
    request: Request, authorization: str | None = Header(default=None)
) -> VerifiedCredential:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _problem(401, "unauthorized")
    verified = await _token_service(request).verify(authorization[7:], "app")
    if verified is None:
        raise _problem(401, "unauthorized")
    return verified


async def require_admin(
    request: Request, cm_admin_session: str | None = Cookie(default=None)
) -> AdminIdentity:
    if not cm_admin_session:
        raise _problem(401, "unauthorized")
    inspected = await _session_service(request).inspect(cm_admin_session, refresh_csrf=False)
    if inspected is None:
        raise _problem(401, "unauthorized")
    session, _ = inspected
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        _validate_origin(request)
        csrf = request.headers.get("x-csrf-token")
        if csrf is None or not secrets.compare_digest(session.csrf_digest, digest(csrf)):
            raise _problem(403, "csrf_rejected")
    return AdminIdentity(session.id, session.token_id)


router = APIRouter(tags=["Authentication"])


@router.get("/api/v1/auth/status", operation_id="getAppAuthStatus")
async def app_status(
    request: Request,
    identity: Annotated[VerifiedCredential, Depends(require_app)],
) -> dict[str, object]:
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        server_instance_id = await uow.session.scalar(select(db.server_identity.c.id).limit(1))
    return {
        "authenticated": True,
        "token_id": identity.public_id,
        "server_time": datetime.now(UTC),
        "server_instance_id": server_instance_id,
        "owner_scope_id": identity.owner_scope_id,
    }


@router.post("/api/v1/admin/auth/session", status_code=201, operation_id="createAdminSession")
async def create_admin_session(
    request: Request, body: AdminLogin, response: Response
) -> dict[str, object]:
    _validate_origin(request)
    client = request.client.host if request.client else "unknown"
    key = "admin-login:" + hashlib.sha256(client.encode()).hexdigest()[:24]
    try:
        created = await _session_service(request).login(body.admin_token, key)
    except PermissionError as error:
        raise _problem(429, "rate_limited") from error
    if created is None:
        raise _problem(401, "unauthorized")
    settings = request.app.state.settings
    response.set_cookie(
        COOKIE_NAME,
        created.cookie,
        secure=settings.admin_session_cookie_secure,
        httponly=True,
        samesite="strict",
        max_age=settings.admin_session_ttl_minutes * 60,
        path="/api/v1/admin",
    )
    return {
        "authenticated": True,
        "csrf_token": created.csrf,
        "created_at": created.session.created_at,
        "expires_at": created.session.expires_at,
    }


@router.get("/api/v1/admin/auth/session", operation_id="getAdminSession")
async def get_admin_session(
    request: Request, cm_admin_session: str | None = Cookie(default=None)
) -> dict[str, object]:
    if not cm_admin_session:
        raise _problem(401, "unauthorized")
    inspected = await _session_service(request).inspect(cm_admin_session, refresh_csrf=True)
    if inspected is None:
        raise _problem(401, "unauthorized")
    session, csrf = inspected
    return {
        "authenticated": True,
        "csrf_token": csrf,
        "created_at": session.created_at,
        "expires_at": session.expires_at,
    }


@router.delete("/api/v1/admin/auth/session", status_code=204, operation_id="deleteAdminSession")
async def delete_admin_session(
    request: Request,
    response: Response,
    cm_admin_session: str | None = Cookie(default=None),
    csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    _validate_origin(request)
    if not cm_admin_session:
        raise _problem(401, "unauthorized")
    if not csrf:
        raise _problem(403, "csrf_rejected")
    try:
        valid = await _session_service(request).logout(cm_admin_session, csrf)
    except PermissionError as error:
        raise _problem(403, "csrf_rejected") from error
    if not valid:
        raise _problem(401, "unauthorized")
    response.delete_cookie(COOKIE_NAME, path="/api/v1/admin")


@router.get("/api/v1/admin/app-credential", operation_id="getAppCredentialStatus")
async def get_app_credential(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        active = list(await uow.access_tokens.list_active("app"))
    if not active:
        raise AppProblem(404, "app_credential_missing", "App Token 不存在", "尚未初始化 App Token")
    token = active[-1]
    return {
        "token_id": token.public_id,
        "status": "active",
        "created_at": token.created_at,
        "rotated_at": token.created_at if token.rotated_from_id else None,
    }


@router.post("/api/v1/admin/app-credential", operation_id="rotateAppCredential")
async def rotate_app_credential(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
    request_digest = hashlib.sha256(b"app-credential-rotate-v1").hexdigest()
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        existing = await uow.idempotency.get_bound(
            "admin", identity.token_id, "app_credential.rotate", key_digest
        )
    if existing is not None:
        raise AppProblem(
            409,
            "app_credential_already_rotated",
            "App Token 已轮换",
            "完整 Token 只在首次轮换时显示一次。如已丢失请再次轮换。",
        )
    issued = await _token_service(request).rotate_app()
    timestamp = datetime.now(UTC)
    async with SqlAlchemyUnitOfWork(request.app.state.database.sessions) as uow:
        await uow.idempotency.add(
            IdempotencyRecord(
                id=str(uuid4()),
                actor_scope="admin",
                actor_id=identity.token_id,
                operation="app_credential.rotate",
                key_digest=key_digest,
                request_digest=request_digest,
                state="completed",
                response_status=200,
                response_body=json.dumps(
                    {"token_id": issued.public_id, "rotated_at": timestamp.isoformat()}
                ),
                resource_id=issued.public_id,
                created_at=timestamp,
                expires_at=timestamp + timedelta(hours=24),
            )
        )
        await uow.commit()
    return {
        "token": issued.value,
        "token_id": issued.public_id,
        "rotated_at": timestamp,
    }
