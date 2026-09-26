"""SQLAlchemy metadata for the Phase 2 business schema."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC as naive SQLite values and always return aware UTC values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("persisted timestamps must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        del dialect
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def utc_timestamp() -> UTCDateTime:
    return UTCDateTime(timezone=True)


access_tokens = Table(
    "access_tokens",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("public_id", String(64), nullable=False, unique=True),
    Column("secret_hash", Text, nullable=False),
    Column("scope", String(16), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("expires_at", utc_timestamp(), nullable=True),
    Column("revoked_at", utc_timestamp(), nullable=True),
    Column("last_used_at", utc_timestamp(), nullable=True),
    Column(
        "rotated_from_id",
        String(36),
        ForeignKey("access_tokens.id", ondelete="SET NULL"),
        nullable=True,
    ),
    CheckConstraint("scope IN ('app', 'admin')", name="scope"),
    CheckConstraint("status IN ('active', 'revoked')", name="status"),
    CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="expiry"),
    CheckConstraint(
        "(status = 'active' AND revoked_at IS NULL) OR "
        "(status = 'revoked' AND revoked_at IS NOT NULL)",
        name="revocation",
    ),
)
Index("ix_access_tokens_scope_status", access_tokens.c.scope, access_tokens.c.status)

admin_sessions = Table(
    "admin_sessions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "token_id",
        String(36),
        ForeignKey("access_tokens.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("session_digest", String(64), nullable=False, unique=True),
    Column("csrf_digest", String(64), nullable=False),
    Column("state", String(16), nullable=False),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("expires_at", utc_timestamp(), nullable=False),
    Column("revoked_at", utc_timestamp(), nullable=True),
    Column("last_seen_at", utc_timestamp(), nullable=True),
    CheckConstraint("state IN ('active', 'revoked')", name="state"),
    CheckConstraint("expires_at > created_at", name="expiry"),
    CheckConstraint(
        "(state = 'active' AND revoked_at IS NULL) OR "
        "(state = 'revoked' AND revoked_at IS NOT NULL)",
        name="revocation",
    ),
)
Index("ix_admin_sessions_token_state", admin_sessions.c.token_id, admin_sessions.c.state)
Index("ix_admin_sessions_expiry", admin_sessions.c.expires_at)

auth_throttle_state = Table(
    "auth_throttle_state",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("throttle_key", String(128), nullable=False, unique=True),
    Column("failed_count", Integer, nullable=False),
    Column("window_started_at", utc_timestamp(), nullable=False),
    Column("blocked_until", utc_timestamp(), nullable=True),
    Column("updated_at", utc_timestamp(), nullable=False),
    CheckConstraint("failed_count >= 0", name="failed_count"),
)

idempotency_records = Table(
    "idempotency_records",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("actor_scope", String(32), nullable=False),
    Column("actor_id", String(64), nullable=False),
    Column("operation", String(96), nullable=False),
    Column("key_digest", String(64), nullable=False),
    Column("request_digest", String(64), nullable=False),
    Column("state", String(16), nullable=False),
    Column("response_status", Integer, nullable=True),
    Column("response_body", Text, nullable=True),
    Column("resource_id", String(36), nullable=True),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("expires_at", utc_timestamp(), nullable=False),
    CheckConstraint("state IN ('processing', 'completed', 'failed')", name="state"),
    CheckConstraint("expires_at > created_at", name="expiry"),
    CheckConstraint(
        "(state = 'processing' AND response_status IS NULL) OR "
        "(state IN ('completed', 'failed') AND response_status IS NOT NULL)",
        name="result",
    ),
)
Index(
    "ux_idempotency_records_binding",
    idempotency_records.c.actor_scope,
    idempotency_records.c.actor_id,
    idempotency_records.c.operation,
    idempotency_records.c.key_digest,
    unique=True,
)
Index("ix_idempotency_records_expiry", idempotency_records.c.expires_at)

stored_objects = Table(
    "stored_objects",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("relative_path", Text, nullable=False, unique=True),
    Column("content_type", String(96), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("width", Integer, nullable=False),
    Column("height", Integer, nullable=False),
    Column("state", String(16), nullable=False),
    Column("asset_ref_count", Integer, nullable=False, server_default="0"),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("verified_at", utc_timestamp(), nullable=True),
    CheckConstraint("length(sha256) = 64", name="sha256_length"),
    CheckConstraint("size_bytes > 0", name="size"),
    CheckConstraint("width > 0 AND height > 0", name="dimensions"),
    CheckConstraint("state IN ('available', 'missing')", name="state"),
    CheckConstraint("asset_ref_count >= 0", name="asset_ref_count"),
)

assets = Table(
    "assets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column(
        "stored_object_id",
        String(36),
        ForeignKey("stored_objects.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("favorite", Boolean, nullable=False, server_default="0"),
    Column("content_state", String(16), nullable=False),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("updated_at", utc_timestamp(), nullable=False),
    Column("deleted_at", utc_timestamp(), nullable=True),
    CheckConstraint("kind IN ('person', 'garment')", name="kind"),
    CheckConstraint("content_state IN ('available', 'deleted')", name="content_state"),
    CheckConstraint(
        "(content_state = 'available' AND stored_object_id IS NOT NULL AND deleted_at IS NULL) OR "
        "(content_state = 'deleted' AND stored_object_id IS NULL AND deleted_at IS NOT NULL)",
        name="content_lifecycle",
    ),
)
Index("ix_assets_list_order", assets.c.created_at.desc(), assets.c.id.desc())
Index("ix_assets_kind_favorite", assets.c.kind, assets.c.favorite)

person_assets = Table(
    "person_assets",
    metadata,
    Column(
        "asset_id", String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    ),
)

garment_assets = Table(
    "garment_assets",
    metadata,
    Column(
        "asset_id", String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("category", String(32), nullable=False),
    Column("source", String(32), nullable=False),
    CheckConstraint(
        "category IN ('upper_body', 'lower_body', 'dress', 'unknown')", name="category"
    ),
    CheckConstraint(
        "source IN ('photo', 'screenshot', 'product_image', 'experimental', 'unknown')",
        name="source",
    ),
)

upload_sessions = Table(
    "upload_sessions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "actor_token_id",
        String(36),
        ForeignKey("access_tokens.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("asset_kind", String(16), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(96), nullable=False),
    Column("expected_size", Integer, nullable=False),
    Column("confirmed_offset", Integer, nullable=False),
    Column("temp_name", String(128), nullable=False, unique=True),
    Column("state", String(16), nullable=False),
    Column("garment_category", String(32), nullable=True),
    Column("garment_source", String(32), nullable=True),
    Column("client_sha256", String(64), nullable=True),
    Column(
        "completed_asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("error_code", String(96), nullable=True),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("updated_at", utc_timestamp(), nullable=False),
    Column("expires_at", utc_timestamp(), nullable=False),
    CheckConstraint("asset_kind IN ('person', 'garment')", name="asset_kind"),
    CheckConstraint(
        "state IN ('created', 'uploading', 'completed', 'failed', 'cancelled')", name="state"
    ),
    CheckConstraint("expected_size > 0", name="expected_size"),
    CheckConstraint(
        "confirmed_offset >= 0 AND confirmed_offset <= expected_size", name="confirmed_offset"
    ),
    CheckConstraint("expires_at > created_at", name="expiry"),
    CheckConstraint(
        "(asset_kind = 'person' AND garment_category IS NULL AND garment_source IS NULL) OR "
        "(asset_kind = 'garment' AND garment_category IS NOT NULL AND garment_source IS NOT NULL)",
        name="subtype_metadata",
    ),
    CheckConstraint(
        "(state = 'completed' AND completed_asset_id IS NOT NULL) OR "
        "(state <> 'completed' AND completed_asset_id IS NULL)",
        name="completion",
    ),
)
Index("ix_upload_sessions_actor_state", upload_sessions.c.actor_token_id, upload_sessions.c.state)
Index("ix_upload_sessions_expiry", upload_sessions.c.expires_at)

asset_references = Table(
    "asset_references",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "asset_id", String(36), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("source_kind", String(64), nullable=False),
    Column("source_id", String(64), nullable=False),
    Column("display_label", String(255), nullable=True),
    Column("active", Boolean, nullable=False, server_default="1"),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("released_at", utc_timestamp(), nullable=True),
    UniqueConstraint("asset_id", "source_kind", "source_id", name="source"),
    CheckConstraint(
        "(active = 1 AND released_at IS NULL) OR (active = 0 AND released_at IS NOT NULL)",
        name="lifecycle",
    ),
)
Index("ix_asset_references_active", asset_references.c.asset_id, asset_references.c.active)

security_audit_events = Table(
    "security_audit_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("action", String(96), nullable=False),
    Column("actor_kind", String(32), nullable=False),
    Column("actor_id", String(64), nullable=True),
    Column("outcome", String(16), nullable=False),
    Column("context_json", Text, nullable=False, server_default="{}"),
    Column("created_at", utc_timestamp(), nullable=False),
    CheckConstraint("outcome IN ('succeeded', 'failed', 'denied')", name="outcome"),
)
Index("ix_security_audit_events_created", security_audit_events.c.created_at)
