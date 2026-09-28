"""Asset, upload, storage, and idempotency entities for Phase 2."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

AssetKind = Literal["person", "garment", "generated_output", "mask"]
ContentState = Literal["available", "deleted"]
UploadState = Literal["created", "uploading", "completed", "failed", "cancelled"]
IdempotencyState = Literal["processing", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class StoredObject:
    id: str
    sha256: str
    relative_path: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    state: Literal["available", "missing"]
    asset_ref_count: int
    created_at: datetime
    verified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PersonMetadata:
    asset_id: str


@dataclass(frozen=True, slots=True)
class GarmentMetadata:
    asset_id: str
    category: Literal["upper_body", "lower_body", "dress", "unknown"]
    source: Literal["photo", "screenshot", "product_image", "experimental", "unknown"]


@dataclass(frozen=True, slots=True)
class Asset:
    id: str
    kind: AssetKind
    stored_object_id: str | None
    favorite: bool
    content_state: ContentState
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    person: PersonMetadata | None = None
    garment: GarmentMetadata | None = None


@dataclass(frozen=True, slots=True)
class UploadSession:
    id: str
    actor_token_id: str
    asset_kind: AssetKind
    filename: str
    content_type: str
    expected_size: int
    confirmed_offset: int
    temp_name: str
    state: UploadState
    created_at: datetime
    expires_at: datetime
    garment_category: str | None = None
    garment_source: str | None = None
    client_sha256: str | None = None
    completed_asset_id: str | None = None
    error_code: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AssetReference:
    id: str
    asset_id: str
    source_kind: str
    source_id: str
    active: bool
    created_at: datetime
    display_label: str | None = None
    released_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    id: str
    actor_scope: str
    actor_id: str
    operation: str
    key_digest: str
    request_digest: str
    state: IdempotencyState
    created_at: datetime
    expires_at: datetime
    response_status: int | None = None
    response_body: str | None = None
    resource_id: str | None = None
