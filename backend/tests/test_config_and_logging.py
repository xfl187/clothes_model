import json
import logging

from pytest import MonkeyPatch

from clothes_model.core.config import Settings
from clothes_model.core.logging import JsonFormatter


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
