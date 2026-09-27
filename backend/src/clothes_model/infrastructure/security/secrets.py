"""Versioned AES-256-GCM envelopes for provider and node secrets."""

import base64
import json
from pathlib import Path
from typing import cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSION = 1
_ALGORITHM = "AES-256-GCM"


class SecretCryptoError(RuntimeError):
    """Secret encryption/decryption failed without exposing sensitive details."""


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64d(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def load_master_key(path: Path | None) -> bytes:
    if path is None:
        raise SecretCryptoError("encryption master key is not configured")
    try:
        encoded = path.read_text(encoding="ascii").strip()
        key = _b64d(encoded)
    except (OSError, UnicodeError, ValueError) as error:
        raise SecretCryptoError("encryption master key is unavailable") from error
    if len(key) != 32:
        raise SecretCryptoError("encryption master key is invalid")
    return key


class AesGcmSecretCipher:
    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise SecretCryptoError("encryption master key is invalid")
        self._cipher = AESGCM(master_key)

    @staticmethod
    def _aad(purpose: str, record_id: str) -> bytes:
        if not purpose or not record_id:
            raise SecretCryptoError("secret binding is invalid")
        return f"clothes-model:v{_VERSION}:{purpose}:{record_id}".encode()

    def encrypt(self, plaintext: str, *, purpose: str, record_id: str) -> str:
        import os

        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(
            nonce, plaintext.encode("utf-8"), self._aad(purpose, record_id)
        )
        envelope = {
            "alg": _ALGORITHM,
            "ciphertext": _b64e(ciphertext),
            "nonce": _b64e(nonce),
            "v": _VERSION,
        }
        return json.dumps(envelope, separators=(",", ":"), sort_keys=True)

    def decrypt(self, envelope: str, *, purpose: str, record_id: str) -> str:
        try:
            decoded: object = json.loads(envelope)
            if not isinstance(decoded, dict):
                raise SecretCryptoError("encrypted secret envelope is invalid")
            raw = cast(dict[str, object], decoded)
            if raw.get("v") != _VERSION or raw.get("alg") != _ALGORITHM:
                raise SecretCryptoError("encrypted secret envelope is unsupported")
            if set(raw) != {"alg", "ciphertext", "nonce", "v"}:
                raise SecretCryptoError("encrypted secret envelope is invalid")
            nonce_value = raw["nonce"]
            ciphertext_value = raw["ciphertext"]
            if not isinstance(nonce_value, str) or not isinstance(ciphertext_value, str):
                raise SecretCryptoError("encrypted secret envelope is invalid")
            nonce = _b64d(nonce_value)
            ciphertext = _b64d(ciphertext_value)
            if len(nonce) != 12:
                raise SecretCryptoError("encrypted secret envelope is invalid")
            plaintext = self._cipher.decrypt(nonce, ciphertext, self._aad(purpose, record_id))
            return plaintext.decode("utf-8")
        except SecretCryptoError:
            raise
        except (
            InvalidTag,
            KeyError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            raise SecretCryptoError("encrypted secret could not be authenticated") from error
