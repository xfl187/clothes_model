"""Persistence ports for provider configuration and immutable revisions."""

from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.providers.domain import (
    ProviderConfig,
    ProviderConfigRevision,
    ProviderDefaultSelection,
)


class ProviderConfigRepository(Protocol):
    async def add_config(self, config: ProviderConfig) -> None: ...

    async def get_config(self, provider_id: str) -> ProviderConfig | None: ...

    async def list_configs(self) -> list[ProviderConfig]: ...

    async def update_config(self, config: ProviderConfig) -> None: ...

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
