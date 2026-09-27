"""Normalized provider failure taxonomy shared by every adapter."""

from typing import Literal

ProviderErrorClass = Literal[
    "temporarily_offline",
    "retryable_transient",
    "invalid_configuration",
    "rejected_input",
    "externally_ambiguous",
    "terminal_failure",
]

RETRYABLE_CLASSES: frozenset[str] = frozenset({"retryable_transient"})
OFFLINE_CLASSES: frozenset[str] = frozenset({"temporarily_offline"})
AMBIGUOUS_CLASSES: frozenset[str] = frozenset({"externally_ambiguous"})
STOPPING_CLASSES: frozenset[str] = frozenset(
    {"invalid_configuration", "rejected_input", "terminal_failure"}
)


class ProviderError(Exception):
    """A provider failure mapped to a stable class without leaking transport details."""

    def __init__(
        self,
        error_class: ProviderErrorClass,
        code: str,
        detail: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(detail)
        self.error_class = error_class
        self.code = code
        self.detail = detail
        self.retryable = retryable
