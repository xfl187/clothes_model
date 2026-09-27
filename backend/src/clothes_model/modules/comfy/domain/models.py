"""Persisted physical ComfyUI node state."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ComfyNodeHealth = Literal["unchecked", "healthy", "offline", "incompatible"]


@dataclass(frozen=True, slots=True)
class ComfyNodeConfig:
    id: str
    endpoint: str
    timeout_seconds: int
    enabled: bool
    health_status: ComfyNodeHealth
    created_at: datetime
    updated_at: datetime
    credential_envelope: str | None = None
    credential_updated_at: datetime | None = None
    health_detail: str | None = None
    observed_server_version: str | None = None
    observed_capabilities_json: str = "{}"
    last_checked_at: datetime | None = None

