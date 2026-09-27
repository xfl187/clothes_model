"""Provider configuration and immutable revision entities for Phase 3."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ProviderType = Literal["llm_image_edit", "comfyui", "unknown"]
ProviderConfigState = Literal["inactive", "validated", "active", "disabled"]


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    id: str
    display_name: str
    provider_type: ProviderType
    state: ProviderConfigState
    created_at: datetime
    updated_at: datetime
    secret_envelope: str | None = None
    secret_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProviderConfigRevision:
    id: str
    provider_id: str
    revision: int
    adapter_type: str
    endpoint: str
    model: str
    timeout_seconds: int
    capabilities_json: str
    created_at: datetime
    vendor_parameters_json: str = "{}"


@dataclass(frozen=True, slots=True)
class ProviderDefaultSelection:
    id: str
    provider_id: str
    config_revision_id: str
    updated_at: datetime
