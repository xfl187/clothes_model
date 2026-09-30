import json
import logging
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from clothes_model.api.application import _load_secret_cipher
from clothes_model.core.config import Settings
from clothes_model.core.logging import JsonFormatter
from clothes_model.infrastructure.security import SecretCryptoError


def test_prefixed_environment_and_safe_log_context(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("CLOTHES_MODEL_ENVIRONMENT", "test")
    monkeypatch.setenv("CLOTHES_MODEL_BIND_PORT", "9010")
    monkeypatch.setenv("CLOTHES_MODEL_ENCRYPTION_MASTER_KEY_FILE", "super-secret-value")
    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.bind_port == 9010
    serialized = json.dumps(settings.safe_log_context())
    assert "super-secret-value" not in serialized
    assert "encryption_master_key" not in serialized


def test_json_formatter_does_not_serialize_unapproved_record_fields() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="event",
        args=(),
        exc_info=None,
    )
    record.provider_secret = "must-not-leak"
    payload = JsonFormatter().format(record)

    assert json.loads(payload)["message"] == "event"
    assert "must-not-leak" not in payload


def test_configured_invalid_master_key_fails_application_startup(tmp_path: Path) -> None:
    key_path = tmp_path / "invalid-master.key"
    key_path.write_bytes(b"x" * 32)

    with pytest.raises(SecretCryptoError, match="encryption master key"):
        _load_secret_cipher(
            Settings(
                _env_file=None,
                environment="test",
                encryption_master_key_file=key_path,
            )
        )
