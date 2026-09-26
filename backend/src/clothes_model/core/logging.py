"""Structured JSON logging with request correlation."""

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str] = ContextVar("request_id", default="system")


def set_request_context(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_context(token: Token[str]) -> None:
    _request_id.reset(token)


def current_trace_id() -> str:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Serialize approved log fields as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": current_trace_id(),
        }
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload["data"] = event_data
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
