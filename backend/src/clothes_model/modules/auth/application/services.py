"""Credential lifecycle and audited secret operations."""

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from clothes_model.infrastructure.security import (
    AesGcmSecretCipher,
    Argon2TokenHasher,
    GeneratedToken,
    SecretCryptoError,
    TokenFormatError,
    generate_token,
    parse_token,
)
from clothes_model.modules.auth.application.ports import AuthUnitOfWork
from clothes_model.modules.auth.domain import AccessToken, SecurityAuditEvent, TokenScope


class AuthUnitOfWorkFactory(Protocol):
    def __call__(self) -> AuthUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class IssuedCredential:
    scope: TokenScope
    public_id: str
    value: str

    def __repr__(self) -> str:
        return (
            f"IssuedCredential(scope={self.scope!r}, public_id={self.public_id!r}, "
            "value='<redacted>')"
        )


@dataclass(frozen=True, slots=True)
class VerifiedCredential:
    token_id: str
    public_id: str
    scope: TokenScope


class TokenService:
    def __init__(
        self,
        uow_factory: AuthUnitOfWorkFactory,
        hasher: Argon2TokenHasher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._hasher = hasher or Argon2TokenHasher()
        self._clock = clock or (lambda: datetime.now(UTC))

    async def bootstrap(self) -> list[IssuedCredential]:
        issued: list[IssuedCredential] = []
        async with self._uow_factory() as uow:
            for scope in ("app", "admin"):
                if await uow.access_tokens.list_active(scope):
                    continue
                generated, record = self._new_token(scope)
                await uow.access_tokens.add(record)
                await self._audit(uow, f"token.{scope}.bootstrap", record.id)
                issued.append(self._issued(generated))
            await uow.commit()
        return issued

    async def reset_admin(self) -> IssuedCredential:
        now = self._clock()
        async with self._uow_factory() as uow:
            for current in await uow.access_tokens.list_active("admin"):
                await uow.access_tokens.replace(replace(current, status="revoked", revoked_at=now))
                await uow.admin_sessions.revoke_for_token(current.id, now)
            generated, record = self._new_token("admin")
            await uow.access_tokens.add(record)
            await self._audit(uow, "token.admin.reset", record.id)
            await uow.commit()
        return self._issued(generated)

    async def rotate_app(self) -> IssuedCredential:
        now = self._clock()
        async with self._uow_factory() as uow:
            active = list(await uow.access_tokens.list_active("app"))
            for current in active:
                await uow.access_tokens.replace(replace(current, status="revoked", revoked_at=now))
            generated, record = self._new_token(
                "app", rotated_from_id=active[-1].id if active else None
            )
            await uow.access_tokens.add(record)
            await self._audit(uow, "token.app.rotate", record.id)
            await uow.commit()
        return self._issued(generated)

    async def revoke_app(self, token_id: str) -> bool:
        now = self._clock()
        async with self._uow_factory() as uow:
            current = await uow.access_tokens.get(token_id)
            if current is None or current.scope != "app" or current.status != "active":
                return False
            await uow.access_tokens.replace(replace(current, status="revoked", revoked_at=now))
            await self._audit(uow, "token.app.revoke", token_id)
            await uow.commit()
        return True

    async def verify(self, presented: str, expected_scope: TokenScope) -> VerifiedCredential | None:
        try:
            parsed = parse_token(presented)
        except TokenFormatError:
            return None
        if parsed.scope != expected_scope:
            return None

        async with self._uow_factory() as uow:
            record = await uow.access_tokens.get_by_public_id(parsed.public_id)
            now = self._clock()
            if (
                record is None
                or record.scope != expected_scope
                or record.status != "active"
                or (record.expires_at is not None and record.expires_at <= now)
                or not self._hasher.verify(record.secret_hash, parsed.secret)
            ):
                return None
            secret_hash = record.secret_hash
            if self._hasher.needs_rehash(secret_hash):
                secret_hash = self._hasher.hash(parsed.secret)
            await uow.access_tokens.replace(
                replace(record, secret_hash=secret_hash, last_used_at=now)
            )
            await uow.commit()
            return VerifiedCredential(record.id, record.public_id, record.scope)

    def _new_token(
        self, scope: TokenScope, rotated_from_id: str | None = None
    ) -> tuple[GeneratedToken, AccessToken]:
        generated = generate_token(scope)
        return generated, AccessToken(
            id=str(uuid4()),
            public_id=generated.public_id,
            secret_hash=self._hasher.hash(generated.secret),
            scope=scope,
            status="active",
            created_at=self._clock(),
            rotated_from_id=rotated_from_id,
        )

    @staticmethod
    def _issued(generated: GeneratedToken) -> IssuedCredential:
        return IssuedCredential(generated.scope, generated.public_id, generated.value)

    async def _audit(self, uow: AuthUnitOfWork, action: str, token_id: str) -> None:
        await uow.security_audit.add(
            SecurityAuditEvent(
                id=str(uuid4()),
                action=action,
                actor_kind="operator",
                actor_id=token_id,
                outcome="succeeded",
                context_json="{}",
                created_at=self._clock(),
            )
        )


class AuditedSecretCipher:
    """Application boundary that records metadata-only cryptographic failures."""

    def __init__(
        self,
        cipher: AesGcmSecretCipher,
        uow_factory: AuthUnitOfWorkFactory,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._cipher = cipher
        self._uow_factory = uow_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    async def encrypt(self, plaintext: str, *, purpose: str, record_id: str) -> str:
        try:
            return self._cipher.encrypt(plaintext, purpose=purpose, record_id=record_id)
        except SecretCryptoError:
            await self._record_failure("secret.encrypt", record_id)
            raise

    async def decrypt(self, envelope: str, *, purpose: str, record_id: str) -> str:
        try:
            return self._cipher.decrypt(envelope, purpose=purpose, record_id=record_id)
        except SecretCryptoError:
            await self._record_failure("secret.decrypt", record_id)
            raise

    async def _record_failure(self, action: str, record_id: str) -> None:
        async with self._uow_factory() as uow:
            await uow.security_audit.add(
                SecurityAuditEvent(
                    id=str(uuid4()),
                    action=action,
                    actor_kind="system",
                    actor_id=record_id,
                    outcome="failed",
                    context_json=json.dumps({"reason": "authentication_failed"}),
                    created_at=self._clock(),
                )
            )
            await uow.commit()
