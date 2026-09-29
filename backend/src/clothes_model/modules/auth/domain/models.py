"""Authentication and security metadata persisted during Phase 2."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

TokenScope = Literal["app", "admin"]
TokenStatus = Literal["active", "revoked"]
SessionState = Literal["active", "revoked"]
AuditOutcome = Literal["succeeded", "failed", "denied"]


@dataclass(frozen=True, slots=True)
class AccessToken:
    id: str
    public_id: str
    secret_hash: str
    scope: TokenScope
    status: TokenStatus
    created_at: datetime
    owner_scope_id: str | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    rotated_from_id: str | None = None


@dataclass(frozen=True, slots=True)
class AdminSession:
    id: str
    token_id: str
    session_digest: str
    csrf_digest: str
    state: SessionState
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthThrottle:
    id: str
    throttle_key: str
    failed_count: int
    window_started_at: datetime
    updated_at: datetime
    blocked_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class SecurityAuditEvent:
    id: str
    action: str
    actor_kind: str
    actor_id: str | None
    outcome: AuditOutcome
    context_json: str
    created_at: datetime
