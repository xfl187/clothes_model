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
    text,
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
    CheckConstraint("kind IN ('person', 'garment', 'generated_output')", name="kind"),
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
    Column("asset_id", String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
)

garment_assets = Table(
    "garment_assets",
    metadata,
    Column("asset_id", String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
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
    Column("asset_id", String(36), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False),
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

provider_configs = Table(
    "provider_configs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("display_name", String(120), nullable=False),
    Column("provider_type", String(32), nullable=False),
    Column("state", String(16), nullable=False),
    Column("secret_envelope", Text, nullable=True),
    Column("secret_updated_at", utc_timestamp(), nullable=True),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("updated_at", utc_timestamp(), nullable=False),
    CheckConstraint(
        "provider_type IN ('llm_image_edit', 'comfyui', 'unknown')", name="provider_type"
    ),
    CheckConstraint("state IN ('inactive', 'validated', 'active', 'disabled')", name="state"),
    CheckConstraint(
        "(secret_envelope IS NULL AND secret_updated_at IS NULL) OR "
        "(secret_envelope IS NOT NULL AND secret_updated_at IS NOT NULL)",
        name="secret_pair",
    ),
)

provider_config_revisions = Table(
    "provider_config_revisions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "provider_id",
        String(36),
        ForeignKey("provider_configs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("revision", Integer, nullable=False),
    Column("adapter_type", String(96), nullable=False),
    Column("endpoint", String(512), nullable=False),
    Column("model", String(160), nullable=False),
    Column("timeout_seconds", Integer, nullable=False),
    Column("vendor_parameters_json", Text, nullable=False, server_default="{}"),
    Column("capabilities_json", Text, nullable=False),
    Column("created_at", utc_timestamp(), nullable=False),
    CheckConstraint("revision >= 1", name="revision"),
    CheckConstraint("timeout_seconds >= 1 AND timeout_seconds <= 3600", name="timeout"),
)
Index(
    "ux_provider_config_revisions_provider_revision",
    provider_config_revisions.c.provider_id,
    provider_config_revisions.c.revision,
    unique=True,
)

provider_default_selection = Table(
    "provider_default_selection",
    metadata,
    Column("id", String(16), primary_key=True),
    Column(
        "provider_id",
        String(36),
        ForeignKey("provider_configs.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "config_revision_id",
        String(36),
        ForeignKey("provider_config_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("updated_at", utc_timestamp(), nullable=False),
    CheckConstraint("id = 'default'", name="singleton"),
)

jobs_block_reason_values = (
    "'provider_offline', 'storage_capacity', 'retry_backoff', "
    "'locked_configuration_unavailable', 'external_state_unknown', "
    "'configuration_invalid', 'unknown'"
)
job_item_state_values = (
    "'queued', 'waiting_provider', 'preparing', 'running', 'needs_attention', "
    "'succeeded', 'failed', 'cancelled'"
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("mode", String(32), nullable=False),
    Column("state", String(24), nullable=False),
    Column("block_reason", String(32), nullable=True),
    Column("blocked_detail", String(500), nullable=True),
    Column("candidate_count", Integer, nullable=False),
    Column("seed", Integer, nullable=True),
    Column("advanced_parameters_json", Text, nullable=False, server_default="{}"),
    Column(
        "garment_asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("mask_asset_id", String(36), nullable=True),
    Column(
        "related_job_id",
        String(36),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "provider_id",
        String(36),
        ForeignKey("provider_configs.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "provider_revision_id",
        String(36),
        ForeignKey("provider_config_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("provider_snapshot_json", Text, nullable=False),
    Column("workflow_version_id", String(36), nullable=True),
    Column("workflow_snapshot_json", Text, nullable=True),
    Column("next_attempt_at", utc_timestamp(), nullable=True),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("updated_at", utc_timestamp(), nullable=False),
    CheckConstraint("mode IN ('precise_try_on', 'unknown')", name="mode"),
    CheckConstraint(
        "state IN ('queued', 'waiting_provider', 'preparing', 'running', "
        "'needs_attention', 'succeeded', 'partially_succeeded', 'failed', 'cancelled')",
        name="state",
    ),
    CheckConstraint(
        f"block_reason IS NULL OR block_reason IN ({jobs_block_reason_values})",
        name="block_reason",
    ),
    CheckConstraint("candidate_count >= 1 AND candidate_count <= 4", name="candidate_count"),
    CheckConstraint(
        "(workflow_version_id IS NULL AND workflow_snapshot_json IS NULL) OR "
        "workflow_version_id IS NOT NULL",
        name="workflow_pair",
    ),
)
Index("ix_jobs_list_order", jobs.c.created_at.desc(), jobs.c.id.desc())
Index("ix_jobs_state", jobs.c.state)

job_person_inputs = Table(
    "job_person_inputs",
    metadata,
    Column("job_id", String(36), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "person_asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("ordinal", Integer, nullable=False),
    Column("created_at", utc_timestamp(), nullable=False),
    CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
)
Index(
    "ux_job_person_inputs_ordinal",
    job_person_inputs.c.job_id,
    job_person_inputs.c.ordinal,
    unique=True,
)

job_items = Table(
    "job_items",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("job_id", String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column(
        "person_asset_id",
        String(36),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("candidate_index", Integer, nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("state", String(24), nullable=False),
    Column("block_reason", String(32), nullable=True),
    Column(
        "retry_of_job_item_id",
        String(36),
        ForeignKey("job_items.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "superseded_by_job_item_id",
        String(36),
        ForeignKey("job_items.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("external_execution_id", String(160), nullable=True),
    Column("error_code", String(96), nullable=True),
    Column("error_json", Text, nullable=True),
    Column("next_attempt_at", utc_timestamp(), nullable=True),
    Column("transient_attempts", Integer, nullable=False, server_default="0"),
    Column("claimant_token", String(64), nullable=True),
    Column("claimed_at", utc_timestamp(), nullable=True),
    Column("lease_expires_at", utc_timestamp(), nullable=True),
    Column("created_at", utc_timestamp(), nullable=False),
    Column("updated_at", utc_timestamp(), nullable=False),
    CheckConstraint(f"state IN ({job_item_state_values})", name="state"),
    CheckConstraint(
        f"block_reason IS NULL OR block_reason IN ({jobs_block_reason_values})",
        name="block_reason",
    ),
    CheckConstraint("candidate_index >= 0", name="candidate_index"),
    CheckConstraint("attempt >= 1", name="attempt"),
    CheckConstraint("transient_attempts >= 0", name="transient_attempts"),
    CheckConstraint(
        "(claimant_token IS NULL AND claimed_at IS NULL AND lease_expires_at IS NULL) OR "
        "(claimant_token IS NOT NULL AND claimed_at IS NOT NULL AND lease_expires_at IS NOT NULL)",
        name="claim",
    ),
    CheckConstraint(
        "lease_expires_at IS NULL OR lease_expires_at > claimed_at", name="lease"
    ),
)
Index("ix_job_items_job_candidate", job_items.c.job_id, job_items.c.candidate_index)
Index(
    "ux_job_items_candidate_attempt",
    job_items.c.job_id,
    job_items.c.candidate_index,
    job_items.c.attempt,
    unique=True,
)
Index(
    "ix_job_items_claim",
    job_items.c.state,
    job_items.c.next_attempt_at,
    job_items.c.lease_expires_at,
)
Index(
    "ux_job_items_active_candidate",
    job_items.c.job_id,
    job_items.c.candidate_index,
    unique=True,
    sqlite_where=text("state NOT IN ('succeeded', 'failed', 'cancelled')"),
)
Index(
    "ux_job_items_external_execution",
    job_items.c.external_execution_id,
    unique=True,
    sqlite_where=text("external_execution_id IS NOT NULL"),
)

generated_outputs = Table(
    "generated_outputs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "job_item_id",
        String(36),
        ForeignKey("job_items.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("asset_id", String(36), ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False),
    Column("favorite", Boolean, nullable=False, server_default="0"),
    Column("seed", Integer, nullable=True),
    Column("actual_parameters_json", Text, nullable=False, server_default="{}"),
    Column("quality_warnings_json", Text, nullable=False, server_default="[]"),
    Column("created_at", utc_timestamp(), nullable=False),
)
Index("ix_generated_outputs_item", generated_outputs.c.job_item_id)
Index("ix_generated_outputs_asset", generated_outputs.c.asset_id)
Index(
    "ux_generated_outputs_item_asset",
    generated_outputs.c.job_item_id,
    generated_outputs.c.asset_id,
    unique=True,
)

job_execution_events = Table(
    "job_execution_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("job_id", String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column(
        "job_item_id",
        String(36),
        ForeignKey("job_items.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("event_type", String(48), nullable=False),
    Column("from_state", String(24), nullable=True),
    Column("to_state", String(24), nullable=True),
    Column("error_code", String(96), nullable=True),
    Column("detail_json", Text, nullable=False, server_default="{}"),
    Column("occurred_at", utc_timestamp(), nullable=False),
)
Index(
    "ix_job_execution_events_job",
    job_execution_events.c.job_id,
    job_execution_events.c.occurred_at,
)
Index(
    "ix_job_execution_events_item",
    job_execution_events.c.job_item_id,
    job_execution_events.c.occurred_at,
)
