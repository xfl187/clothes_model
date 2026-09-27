"""Admin browser-session lifecycle and persistent login throttling."""

import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from clothes_model.modules.auth.application.services import AuthUnitOfWorkFactory, TokenService
from clothes_model.modules.auth.domain import AdminSession, AuthThrottle


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class NewAdminSession:
    cookie: str
    csrf: str
    session: AdminSession


class AdminSessionService:
    def __init__(
        self,
        uow_factory: AuthUnitOfWorkFactory,
        token_service: TokenService,
        *,
        ttl_minutes: int,
        max_failures: int,
        window_seconds: int,
    ) -> None:
        self._uow_factory, self._tokens = uow_factory, token_service
        self._ttl, self._max_failures = timedelta(minutes=ttl_minutes), max_failures
        self._window = timedelta(seconds=window_seconds)

    async def login(self, token: str, throttle_key: str) -> NewAdminSession | None:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            throttle = await uow.auth_throttles.get_by_key(throttle_key)
            if throttle and throttle.blocked_until and throttle.blocked_until > now:
                raise PermissionError("rate_limited")
        verified = await self._tokens.verify(token, "admin")
        if verified is None:
            await self._failed_login(throttle_key, now)
            return None
        cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        session = AdminSession(
            str(uuid4()),
            verified.token_id,
            digest(cookie),
            digest(csrf),
            "active",
            now,
            now + self._ttl,
        )
        async with self._uow_factory() as uow:
            await uow.admin_sessions.add(session)
            throttle = await uow.auth_throttles.get_by_key(throttle_key)
            if throttle:
                await uow.auth_throttles.replace(
                    replace(throttle, failed_count=0, blocked_until=None, updated_at=now)
                )
            await uow.commit()
        return NewAdminSession(cookie, csrf, session)

    async def inspect(self, cookie: str, *, refresh_csrf: bool) -> tuple[AdminSession, str] | None:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await uow.admin_sessions.get_by_digest(digest(cookie))
            if session is None or session.state != "active":
                return None
            if session.expires_at <= now:
                await uow.admin_sessions.replace(replace(session, state="revoked", revoked_at=now))
                await uow.commit()
                return None
            csrf = secrets.token_urlsafe(32) if refresh_csrf else ""
            if refresh_csrf:
                session = replace(session, csrf_digest=digest(csrf), last_seen_at=now)
                await uow.admin_sessions.replace(session)
                await uow.commit()
            return session, csrf

    async def logout(self, cookie: str, csrf: str) -> bool:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await uow.admin_sessions.get_by_digest(digest(cookie))
            if session is None or session.state != "active" or session.expires_at <= now:
                return False
            if not secrets.compare_digest(session.csrf_digest, digest(csrf)):
                raise PermissionError("csrf_rejected")
            await uow.admin_sessions.replace(
                replace(session, state="revoked", revoked_at=now, last_seen_at=now)
            )
            await uow.commit()
            return True

    async def _failed_login(self, key: str, now: datetime) -> None:
        async with self._uow_factory() as uow:
            current = await uow.auth_throttles.get_by_key(key)
            if current is None or current.window_started_at + self._window <= now:
                await uow.auth_throttles.add(AuthThrottle(str(uuid4()), key, 1, now, now))
            else:
                count = current.failed_count + 1
                blocked = now + self._window if count >= self._max_failures else None
                await uow.auth_throttles.replace(
                    replace(current, failed_count=count, blocked_until=blocked, updated_at=now)
                )
            await uow.commit()
