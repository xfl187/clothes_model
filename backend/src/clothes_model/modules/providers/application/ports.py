"""Persistence and adapter ports for provider configuration and execution."""

from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
    ProviderDefaultSelection,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
    ProviderStatusResult,
    ProviderSubmission,
)


class ProviderAdapter(Protocol):
    """Adapter-local transport behind the provider application port."""

    @property
    def adapter_type(self) -> str: ...

    async def availability(self, invocation: ProviderInvocation) -> str: ...

    async def capabilities(self, invocation: ProviderInvocation) -> ProviderCapabilities: ...

    async def validate(self, invocation: ProviderInvocation) -> None: ...

    async def submit(
        self, invocation: ProviderInvocation, request: ProviderRequest
    ) -> ProviderSubmission: ...

    async def query(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> ProviderStatusResult: ...

    async def cancel(self, invocation: ProviderInvocation, external_execution_id: str) -> bool: ...

    async def fetch_outputs(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> list[ProviderOutput]: ...


class ProviderRegistryPort(Protocol):
    def resolve(self, adapter_type: str) -> ProviderAdapter: ...


class ProviderConfigRepository(Protocol):
    async def add_config(self, config: ProviderConfig) -> None: ...

    async def get_config(self, provider_id: str) -> ProviderConfig | None: ...

    async def list_configs(self) -> list[ProviderConfig]: ...

    async def update_config(self, config: ProviderConfig) -> None: ...

    async def has_references(self, provider_id: str) -> bool: ...

    async def delete_config(self, provider_id: str) -> None: ...

    async def add_revision(self, revision: ProviderConfigRevision) -> None: ...

    async def get_revision(self, revision_id: str) -> ProviderConfigRevision | None: ...

    async def list_revisions(self, provider_id: str) -> list[ProviderConfigRevision]: ...

    async def get_current_revision(self, provider_id: str) -> ProviderConfigRevision | None: ...

    async def set_default(self, selection: ProviderDefaultSelection) -> None: ...

    async def get_default(self) -> ProviderDefaultSelection | None: ...

    async def clear_default(self) -> None: ...


class ProviderUnitOfWork(UnitOfWork, Protocol):
    """Provider repositories sharing the service-wide transaction boundary."""

    @property
    def provider_configs(self) -> ProviderConfigRepository: ...
