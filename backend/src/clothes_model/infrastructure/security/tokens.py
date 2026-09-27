"""Opaque token generation, parsing, and slow hashing."""

import base64
import secrets
from dataclasses import dataclass
from typing import Literal, cast

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

TokenScope = Literal["app", "admin"]
_PREFIX = "cm"
_PUBLIC_BYTES = 12
_SECRET_BYTES = 32


class TokenFormatError(ValueError):
    """A presented credential is not a supported opaque token."""


@dataclass(frozen=True, slots=True)
class GeneratedToken:
    value: str
    public_id: str
    secret: str
    scope: TokenScope

    def __repr__(self) -> str:
        return (
            f"GeneratedToken(scope={self.scope!r}, public_id={self.public_id!r}, "
            "value='<redacted>')"
        )


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def generate_token(scope: TokenScope) -> GeneratedToken:
    public_id = _encode(secrets.token_bytes(_PUBLIC_BYTES))
    secret = _encode(secrets.token_bytes(_SECRET_BYTES))
    return GeneratedToken(
        value=f"{_PREFIX}.{scope}.{public_id}.{secret}",
        public_id=public_id,
        secret=secret,
        scope=scope,
    )


def parse_token(value: str) -> GeneratedToken:
    parts = value.split(".")
    if len(parts) != 4 or parts[0] != _PREFIX or parts[1] not in {"app", "admin"}:
        raise TokenFormatError("invalid credential")
    scope = cast(TokenScope, parts[1])
    public_id, secret = parts[2], parts[3]
    if len(public_id) != 16 or len(secret) != 43:
        raise TokenFormatError("invalid credential")
    try:
        public_raw = _decode(public_id)
        secret_raw = _decode(secret)
    except (ValueError, UnicodeEncodeError) as error:
        raise TokenFormatError("invalid credential") from error
    if len(public_raw) != _PUBLIC_BYTES or len(secret_raw) != _SECRET_BYTES:
        raise TokenFormatError("invalid credential")
    if _encode(public_raw) != public_id or _encode(secret_raw) != secret:
        raise TokenFormatError("invalid credential")
    return GeneratedToken(value=value, public_id=public_id, secret=secret, scope=scope)


class Argon2TokenHasher:
    """Argon2id policy used for high-entropy App/Admin token secrets."""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=2,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, secret: str) -> str:
        return self._hasher.hash(secret)

    def verify(self, encoded_hash: str, secret: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, secret)
        except VerificationError, InvalidHashError:
            return False

    def needs_rehash(self, encoded_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded_hash)
        except InvalidHashError:
            return False
