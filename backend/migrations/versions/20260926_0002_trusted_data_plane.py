"""Add the Phase 2 authentication, upload, storage, and asset schema.

Revision ID: 20260926_0002
Revises: 20260924_0001
Create Date: 2026-09-26
"""

from alembic import op

revision: str = "20260926_0002"
down_revision: str | None = "20260924_0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE access_tokens (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          public_id VARCHAR(64) NOT NULL,
          secret_hash TEXT NOT NULL,
          scope VARCHAR(16) NOT NULL CHECK (scope IN ('app', 'admin')),
          status VARCHAR(16) NOT NULL CHECK (status IN ('active', 'revoked')),
          created_at DATETIME NOT NULL,
          expires_at DATETIME,
          revoked_at DATETIME,
          last_used_at DATETIME,
          rotated_from_id VARCHAR(36),
          CONSTRAINT uq_access_tokens_public_id UNIQUE (public_id),
          CONSTRAINT fk_access_tokens_rotated_from_id_access_tokens
            FOREIGN KEY (rotated_from_id) REFERENCES access_tokens(id) ON DELETE SET NULL,
          CONSTRAINT ck_access_tokens_expiry CHECK (expires_at IS NULL OR expires_at > created_at),
          CONSTRAINT ck_access_tokens_revocation CHECK (
            (status = 'active' AND revoked_at IS NULL) OR
            (status = 'revoked' AND revoked_at IS NOT NULL)
          )
        )
        """,
        "CREATE INDEX ix_access_tokens_scope_status ON access_tokens(scope, status)",
        """
        CREATE TABLE admin_sessions (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          token_id VARCHAR(36) NOT NULL,
          session_digest VARCHAR(64) NOT NULL,
          csrf_digest VARCHAR(64) NOT NULL,
          state VARCHAR(16) NOT NULL CHECK (state IN ('active', 'revoked')),
          created_at DATETIME NOT NULL,
          expires_at DATETIME NOT NULL,
          revoked_at DATETIME,
          last_seen_at DATETIME,
          CONSTRAINT uq_admin_sessions_session_digest UNIQUE (session_digest),
          CONSTRAINT fk_admin_sessions_token_id_access_tokens
            FOREIGN KEY (token_id) REFERENCES access_tokens(id) ON DELETE RESTRICT,
          CONSTRAINT ck_admin_sessions_expiry CHECK (expires_at > created_at),
          CONSTRAINT ck_admin_sessions_revocation CHECK (
            (state = 'active' AND revoked_at IS NULL) OR
            (state = 'revoked' AND revoked_at IS NOT NULL)
          )
        )
        """,
        "CREATE INDEX ix_admin_sessions_token_state ON admin_sessions(token_id, state)",
        "CREATE INDEX ix_admin_sessions_expiry ON admin_sessions(expires_at)",
        """
        CREATE TABLE auth_throttle_state (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          throttle_key VARCHAR(128) NOT NULL,
          failed_count INTEGER NOT NULL CHECK (failed_count >= 0),
          window_started_at DATETIME NOT NULL,
          blocked_until DATETIME,
          updated_at DATETIME NOT NULL,
          CONSTRAINT uq_auth_throttle_state_throttle_key UNIQUE (throttle_key)
        )
        """,
        """
        CREATE TABLE idempotency_records (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          actor_scope VARCHAR(32) NOT NULL,
          actor_id VARCHAR(64) NOT NULL,
          operation VARCHAR(96) NOT NULL,
          key_digest VARCHAR(64) NOT NULL,
          request_digest VARCHAR(64) NOT NULL,
          state VARCHAR(16) NOT NULL CHECK (state IN ('processing', 'completed', 'failed')),
          response_status INTEGER,
          response_body TEXT,
          resource_id VARCHAR(36),
          created_at DATETIME NOT NULL,
          expires_at DATETIME NOT NULL,
          CONSTRAINT ck_idempotency_records_expiry CHECK (expires_at > created_at),
          CONSTRAINT ck_idempotency_records_result CHECK (
            (state = 'processing' AND response_status IS NULL) OR
            (state IN ('completed', 'failed') AND response_status IS NOT NULL)
          )
        )
        """,
        """
        CREATE UNIQUE INDEX ux_idempotency_records_binding
        ON idempotency_records(actor_scope, actor_id, operation, key_digest)
        """,
        "CREATE INDEX ix_idempotency_records_expiry ON idempotency_records(expires_at)",
        """
        CREATE TABLE stored_objects (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          sha256 VARCHAR(64) NOT NULL CHECK (length(sha256) = 64),
          relative_path TEXT NOT NULL,
          content_type VARCHAR(96) NOT NULL,
          size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
          width INTEGER NOT NULL,
          height INTEGER NOT NULL,
          state VARCHAR(16) NOT NULL CHECK (state IN ('available', 'missing')),
          asset_ref_count INTEGER NOT NULL DEFAULT 0 CHECK (asset_ref_count >= 0),
          created_at DATETIME NOT NULL,
          verified_at DATETIME,
          CONSTRAINT uq_stored_objects_sha256 UNIQUE (sha256),
          CONSTRAINT uq_stored_objects_relative_path UNIQUE (relative_path),
          CONSTRAINT ck_stored_objects_dimensions CHECK (width > 0 AND height > 0)
        )
        """,
        """
        CREATE TABLE assets (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          kind VARCHAR(16) NOT NULL CHECK (kind IN ('person', 'garment')),
          stored_object_id VARCHAR(36),
          favorite BOOLEAN NOT NULL DEFAULT 0,
          content_state VARCHAR(16) NOT NULL CHECK (content_state IN ('available', 'deleted')),
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          deleted_at DATETIME,
          CONSTRAINT fk_assets_stored_object_id_stored_objects
            FOREIGN KEY (stored_object_id) REFERENCES stored_objects(id) ON DELETE RESTRICT,
          CONSTRAINT ck_assets_content_lifecycle CHECK (
            (content_state = 'available' AND stored_object_id IS NOT NULL AND deleted_at IS NULL) OR
            (content_state = 'deleted' AND stored_object_id IS NULL AND deleted_at IS NOT NULL)
          )
        )
        """,
        "CREATE INDEX ix_assets_list_order ON assets(created_at DESC, id DESC)",
        "CREATE INDEX ix_assets_kind_favorite ON assets(kind, favorite)",
        """
        CREATE TABLE person_assets (
          asset_id VARCHAR(36) PRIMARY KEY NOT NULL,
          CONSTRAINT fk_person_assets_asset_id_assets
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE garment_assets (
          asset_id VARCHAR(36) PRIMARY KEY NOT NULL,
          category VARCHAR(32) NOT NULL CHECK (
            category IN ('upper_body', 'lower_body', 'dress', 'unknown')
          ),
          source VARCHAR(32) NOT NULL CHECK (
            source IN ('photo', 'screenshot', 'product_image', 'experimental', 'unknown')
          ),
          CONSTRAINT fk_garment_assets_asset_id_assets
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE upload_sessions (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          actor_token_id VARCHAR(36) NOT NULL,
          asset_kind VARCHAR(16) NOT NULL CHECK (asset_kind IN ('person', 'garment')),
          filename VARCHAR(255) NOT NULL,
          content_type VARCHAR(96) NOT NULL,
          expected_size INTEGER NOT NULL CHECK (expected_size > 0),
          confirmed_offset INTEGER NOT NULL,
          temp_name VARCHAR(128) NOT NULL,
          state VARCHAR(16) NOT NULL CHECK (
            state IN ('created', 'uploading', 'completed', 'failed', 'cancelled')
          ),
          garment_category VARCHAR(32),
          garment_source VARCHAR(32),
          client_sha256 VARCHAR(64),
          completed_asset_id VARCHAR(36),
          error_code VARCHAR(96),
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          expires_at DATETIME NOT NULL,
          CONSTRAINT uq_upload_sessions_temp_name UNIQUE (temp_name),
          CONSTRAINT fk_upload_sessions_actor_token_id_access_tokens
            FOREIGN KEY (actor_token_id) REFERENCES access_tokens(id) ON DELETE RESTRICT,
          CONSTRAINT fk_upload_sessions_completed_asset_id_assets
            FOREIGN KEY (completed_asset_id) REFERENCES assets(id) ON DELETE SET NULL,
          CONSTRAINT ck_upload_sessions_offset CHECK (
            confirmed_offset >= 0 AND confirmed_offset <= expected_size
          ),
          CONSTRAINT ck_upload_sessions_expiry CHECK (expires_at > created_at),
          CONSTRAINT ck_upload_sessions_subtype_metadata CHECK (
            (asset_kind = 'person' AND garment_category IS NULL AND garment_source IS NULL) OR
            (asset_kind = 'garment' AND garment_category IS NOT NULL AND garment_source IS NOT NULL)
          ),
          CONSTRAINT ck_upload_sessions_completion CHECK (
            (state = 'completed' AND completed_asset_id IS NOT NULL) OR
            (state <> 'completed' AND completed_asset_id IS NULL)
          )
        )
        """,
        "CREATE INDEX ix_upload_sessions_actor_state ON upload_sessions(actor_token_id, state)",
        "CREATE INDEX ix_upload_sessions_expiry ON upload_sessions(expires_at)",
        """
        CREATE TABLE asset_references (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          asset_id VARCHAR(36) NOT NULL,
          source_kind VARCHAR(64) NOT NULL,
          source_id VARCHAR(64) NOT NULL,
          display_label VARCHAR(255),
          active BOOLEAN NOT NULL DEFAULT 1,
          created_at DATETIME NOT NULL,
          released_at DATETIME,
          CONSTRAINT source UNIQUE (asset_id, source_kind, source_id),
          CONSTRAINT fk_asset_references_asset_id_assets
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE RESTRICT,
          CONSTRAINT ck_asset_references_lifecycle CHECK (
            (active = 1 AND released_at IS NULL) OR
            (active = 0 AND released_at IS NOT NULL)
          )
        )
        """,
        "CREATE INDEX ix_asset_references_active ON asset_references(asset_id, active)",
        """
        CREATE TABLE security_audit_events (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          action VARCHAR(96) NOT NULL,
          actor_kind VARCHAR(32) NOT NULL,
          actor_id VARCHAR(64),
          outcome VARCHAR(16) NOT NULL CHECK (outcome IN ('succeeded', 'failed', 'denied')),
          context_json TEXT NOT NULL DEFAULT '{}',
          created_at DATETIME NOT NULL
        )
        """,
        "CREATE INDEX ix_security_audit_events_created ON security_audit_events(created_at)",
        """
        CREATE TRIGGER ck_person_asset_kind
        BEFORE INSERT ON person_assets
        BEGIN
          SELECT CASE WHEN (SELECT kind FROM assets WHERE id = NEW.asset_id) <> 'person'
            THEN RAISE(ABORT, 'person asset kind mismatch') END;
          SELECT CASE WHEN EXISTS (
            SELECT 1 FROM garment_assets WHERE asset_id = NEW.asset_id
          ) THEN RAISE(ABORT, 'asset already has a garment subtype') END;
        END
        """,
        """
        CREATE TRIGGER ck_garment_asset_kind
        BEFORE INSERT ON garment_assets
        BEGIN
          SELECT CASE WHEN (SELECT kind FROM assets WHERE id = NEW.asset_id) <> 'garment'
            THEN RAISE(ABORT, 'garment asset kind mismatch') END;
          SELECT CASE WHEN EXISTS (
            SELECT 1 FROM person_assets WHERE asset_id = NEW.asset_id
          ) THEN RAISE(ABORT, 'asset already has a person subtype') END;
        END
        """,
        """
        CREATE TRIGGER ck_asset_kind_immutable
        BEFORE UPDATE OF kind ON assets
        WHEN NEW.kind <> OLD.kind
        BEGIN
          SELECT RAISE(ABORT, 'asset kind is immutable');
        END
        """,
        """
        CREATE TRIGGER stored_object_ref_after_asset_insert
        AFTER INSERT ON assets
        WHEN NEW.stored_object_id IS NOT NULL
        BEGIN
          UPDATE stored_objects SET asset_ref_count = asset_ref_count + 1
          WHERE id = NEW.stored_object_id;
        END
        """,
        """
        CREATE TRIGGER stored_object_ref_after_asset_update
        AFTER UPDATE OF stored_object_id ON assets
        WHEN OLD.stored_object_id IS NOT NEW.stored_object_id
        BEGIN
          UPDATE stored_objects SET asset_ref_count = asset_ref_count - 1
          WHERE id = OLD.stored_object_id;
          UPDATE stored_objects SET asset_ref_count = asset_ref_count + 1
          WHERE id = NEW.stored_object_id;
        END
        """,
        """
        CREATE TRIGGER stored_object_ref_after_asset_delete
        AFTER DELETE ON assets
        WHEN OLD.stored_object_id IS NOT NULL
        BEGIN
          UPDATE stored_objects SET asset_ref_count = asset_ref_count - 1
          WHERE id = OLD.stored_object_id;
        END
        """,
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    for trigger in (
        "stored_object_ref_after_asset_delete",
        "stored_object_ref_after_asset_update",
        "stored_object_ref_after_asset_insert",
        "ck_asset_kind_immutable",
        "ck_garment_asset_kind",
        "ck_person_asset_kind",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")

    for table in (
        "security_audit_events",
        "asset_references",
        "upload_sessions",
        "garment_assets",
        "person_assets",
        "assets",
        "stored_objects",
        "idempotency_records",
        "auth_throttle_state",
        "admin_sessions",
        "access_tokens",
    ):
        op.drop_table(table)
