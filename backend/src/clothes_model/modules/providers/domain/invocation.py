"""Provider invocation DTOs shared by the port, adapters, and the execution service."""

from dataclasses import dataclass, field
from typing import Literal

from clothes_model.modules.providers.domain.errors import ProviderError

ProviderExecutionState = Literal["running", "succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class ProviderInvocation:
    provider_id: str
    config_revision_id: str
    adapter_type: str
    endpoint: str
    model: str
    timeout_seconds: int
    vendor_parameters: dict[str, object] = field(default_factory=lambda: {})
    credential: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    job_item_id: str
    candidate_index: int
    candidate_count: int
    seed: int | None
    person_bytes: bytes
    garment_bytes: bytes
    mask_bytes: bytes | None = None


@dataclass(frozen=True, slots=True)
class ProviderSubmission:
    external_execution_id: str


@dataclass(frozen=True, slots=True)
class ProviderStatusResult:
    state: ProviderExecutionState
    error: ProviderError | None = None


@dataclass(frozen=True, slots=True)
class ProviderOutput:
    content: bytes
    content_type: str
    seed: int | None = None
    actual_parameters: dict[str, object] = field(default_factory=lambda: {})
