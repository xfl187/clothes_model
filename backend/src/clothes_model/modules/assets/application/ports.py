"""Persistence ports used by future asset and upload application services."""

from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.assets.domain import (
    Asset,
    AssetReference,
    IdempotencyRecord,
    StoredObject,
    UploadSession,
)


class IdempotencyRepository(Protocol):
    async def add(self, record: IdempotencyRecord) -> None: ...

    async def get_bound(
        self, actor_scope: str, actor_id: str, operation: str, key_digest: str
    ) -> IdempotencyRecord | None: ...


class StoredObjectRepository(Protocol):
    async def add(self, stored_object: StoredObject) -> None: ...

    async def get(self, object_id: str) -> StoredObject | None: ...

    async def get_by_hash(self, sha256: str) -> StoredObject | None: ...


class UploadRepository(Protocol):
    async def add(self, upload: UploadSession) -> None: ...

    async def get(self, upload_id: str) -> UploadSession | None: ...


class AssetRepository(Protocol):
    async def add(self, asset: Asset) -> None: ...

    async def get(self, asset_id: str) -> Asset | None: ...


class AssetReferenceRepository(Protocol):
    async def add(self, reference: AssetReference) -> None: ...

    async def list_active(self, asset_id: str) -> list[AssetReference]: ...


class AssetUnitOfWork(UnitOfWork, Protocol):
    """Asset repositories sharing the service-wide transaction boundary."""

    @property
    def idempotency(self) -> IdempotencyRepository: ...

    @property
    def stored_objects(self) -> StoredObjectRepository: ...

    @property
    def uploads(self) -> UploadRepository: ...

    @property
    def assets(self) -> AssetRepository: ...

    @property
    def asset_references(self) -> AssetReferenceRepository: ...
