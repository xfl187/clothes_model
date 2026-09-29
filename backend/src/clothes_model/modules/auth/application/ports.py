"""Persistence ports used by future authentication application services."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.auth.domain import (
    AccessToken,
    AdminSession,
    AuthThrottle,
    SecurityAuditEvent,
)


class AccessTokenRepository(Protocol):
    async def add(self, token: AccessToken) -> None: ...

    async def get(self, token_id: str) -> AccessToken | None: ...

    async def get_by_public_id(self, public_id: str) -> AccessToken | None: ...

    async def list_active(self, scope: str) -> Sequence[AccessToken]: ...

    async def replace(self, token: AccessToken) -> None: ...


class AdminSessionRepository(Protocol):
    async def add(self, session: AdminSession) -> None: ...

    async def get(self, session_id: str) -> AdminSession | None: ...

    async def get_by_digest(self, digest: str) -> AdminSession | None: ...

    async def revoke_for_token(self, token_id: str, revoked_at: datetime) -> None: ...

    async def replace(self, session: AdminSession) -> None: ...


class AuthThrottleRepository(Protocol):
    async def add(self, throttle: AuthThrottle) -> None: ...

    async def get_by_key(self, throttle_key: str) -> AuthThrottle | None: ...

    async def replace(self, throttle: AuthThrottle) -> None: ...


class SecurityAuditRepository(Protocol):
    async def add(self, event: SecurityAuditEvent) -> None: ...


class OwnerScopeRepository(Protocol):
    async def get_or_create(self, default_id: str, created_at: datetime) -> str: ...


class ServerIdentityRepository(Protocol):
    async def get_or_create(self, default_id: str, created_at: datetime) -> str: ...


class AuthUnitOfWork(UnitOfWork, Protocol):
    """Auth repositories sharing the service-wide transaction boundary."""

    @property
    def access_tokens(self) -> AccessTokenRepository: ...

    @property
    def owner_scopes(self) -> OwnerScopeRepository: ...

    @property
    def server_identity(self) -> ServerIdentityRepository: ...

    @property
    def admin_sessions(self) -> AdminSessionRepository: ...

    @property
    def auth_throttles(self) -> AuthThrottleRepository: ...

    @property
    def security_audit(self) -> SecurityAuditRepository: ...
