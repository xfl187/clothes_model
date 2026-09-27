"""Provider domain entities, capabilities, and failure taxonomy."""

from clothes_model.modules.providers.domain.capabilities import ProviderCapabilities
from clothes_model.modules.providers.domain.errors import (
    AMBIGUOUS_CLASSES,
    OFFLINE_CLASSES,
    RETRYABLE_CLASSES,
    STOPPING_CLASSES,
    ProviderError,
    ProviderErrorClass,
)
from clothes_model.modules.providers.domain.invocation import (
    ProviderExecutionState,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
    ProviderStatusResult,
    ProviderSubmission,
)
from clothes_model.modules.providers.domain.models import (
    ProviderConfig,
    ProviderConfigRevision,
    ProviderConfigState,
    ProviderDefaultSelection,
    ProviderType,
)

__all__ = [
    "AMBIGUOUS_CLASSES",
    "OFFLINE_CLASSES",
    "RETRYABLE_CLASSES",
    "STOPPING_CLASSES",
    "ProviderCapabilities",
    "ProviderConfig",
    "ProviderConfigRevision",
    "ProviderConfigState",
    "ProviderDefaultSelection",
    "ProviderError",
    "ProviderErrorClass",
    "ProviderExecutionState",
    "ProviderInvocation",
    "ProviderOutput",
    "ProviderRequest",
    "ProviderStatusResult",
    "ProviderSubmission",
    "ProviderType",
]
