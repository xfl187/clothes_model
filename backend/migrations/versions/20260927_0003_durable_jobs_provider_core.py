"""Add durable jobs, provider configuration, and generated-output persistence.

Revision ID: 20260927_0003
Revises: 20260926_0002
Create Date: 2026-09-27
"""

from alembic import op

revision: str = "20260927_0003"
down_revision: str | None = "20260926_0002"
branch_labels: str | None = None
depends_on: str | None = None

BLOCK_REASONS = (
    "'provider_offline', 'storage_capacity', 'retry_backoff', "
    "'locked_configuration_unavailable', 'external_state_unknown', "
    "'configuration_invalid', 'unknown'"
)
JOB_ITEM_STATES = (
    "'queued', 'waiting_provider', 'preparing', 'running', 'needs_attention', "
    "'succeeded', 'failed', 'cancelled'"
)
ACTIVE_ITEM_STATES = "('succeeded', 'failed', 'cancelled')"

ASSET_COLUMNS = (
    "id, kind, stored_object_id, favorite, content_state, created_at, updated_at, deleted_at"
)


def _create_assets_table(name: str, kind_check: str) -> str:
    return f"""
        CREATE TABLE {name} (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          kind VARCHAR(16) NOT NULL CHECK (kind IN ({kind_check})),
          stored_object_id VARCHAR(36),
          favorite BOOLEAN NOT NULL DEFAULT 0,
          content_state VARCHAR(16) NOT NULL CHECK (content_state IN ('available', 'deleted')),
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          deleted_at DATETIME,
          CONSTRAINT fk_{name}_stored_object_id_stored_objects
            FOREIGN KEY (stored_object_id) REFERENCES stored_objects(id) ON DELETE RESTRICT,
          CONSTRAINT ck_{name}_content_lifecycle CHECK (
            (content_state = 'available' AND stored_object_id IS NOT NULL AND deleted_at IS NULL) OR
            (content_state = 'deleted' AND stored_object_id IS NULL AND deleted_at IS NOT NULL)
          )
        )
    """


def _create_asset_triggers(prefix: str, table: str) -> tuple[str, ...]:
    return (
        f"""
        CREATE TRIGGER {prefix}ck_asset_kind_immutable
        BEFORE UPDATE OF kind ON {table}
        WHEN NEW.kind <> OLD.kind
        BEGIN
          SELECT RAISE(ABORT, 'asset kind is immutable');
        END
        """,
        f"""
        CREATE TRIGGER {prefix}stored_object_ref_after_asset_insert
        AFTER INSERT ON {table}
        WHEN NEW.stored_object_id IS NOT NULL
        BEGIN
          UPDATE stored_objects SET asset_ref_count = asset_ref_count + 1
          WHERE id = NEW.stored_object_id;
        END
        """,
        f"""
        CREATE TRIGGER {prefix}stored_object_ref_after_asset_update
        AFTER UPDATE OF stored_object_id ON {table}
        WHEN OLD.stored_object_id IS NOT NEW.stored_object_id
        BEGIN
          UPDATE stored_objects SET asset_ref_count = asset_ref_count - 1
          WHERE id = OLD.stored_object_id;
          UPDATE stored_objects SET asset_ref_count = asset_ref_count + 1
          WHERE id = NEW.stored_object_id;
        END
        """,
        f"""
        CREATE TRIGGER {prefix}stored_object_ref_after_asset_delete
        AFTER DELETE ON {table}
        WHEN OLD.stored_object_id IS NOT NULL
        BEGIN
          UPDATE stored_objects SET asset_ref_count = asset_ref_count - 1
          WHERE id = OLD.stored_object_id;
        END
        """,
    )


def _drop_asset_triggers() -> None:
    for trigger in (
        "stored_object_ref_after_asset_delete",
        "stored_object_ref_after_asset_update",
        "stored_object_ref_after_asset_insert",
        "ck_asset_kind_immutable",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE provider_configs (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          display_name VARCHAR(120) NOT NULL,
          provider_type VARCHAR(32) NOT NULL CHECK (
            provider_type IN ('llm_image_edit', 'comfyui', 'unknown')
          ),
          state VARCHAR(16) NOT NULL CHECK (
            state IN ('inactive', 'validated', 'active', 'disabled')
          ),
          secret_envelope TEXT,
          secret_updated_at DATETIME,
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          CONSTRAINT ck_provider_configs_secret_pair CHECK (
            (secret_envelope IS NULL AND secret_updated_at IS NULL) OR
            (secret_envelope IS NOT NULL AND secret_updated_at IS NOT NULL)
          )
        )
        """,
        """
        CREATE TABLE provider_config_revisions (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          provider_id VARCHAR(36) NOT NULL,
          revision INTEGER NOT NULL CHECK (revision >= 1),
          adapter_type VARCHAR(96) NOT NULL,
          endpoint VARCHAR(512) NOT NULL,
          model VARCHAR(160) NOT NULL,
          timeout_seconds INTEGER NOT NULL CHECK (
            timeout_seconds >= 1 AND timeout_seconds <= 3600
          ),
          vendor_parameters_json TEXT NOT NULL DEFAULT '{}',
          capabilities_json TEXT NOT NULL,
          created_at DATETIME NOT NULL,
          CONSTRAINT fk_provider_config_revisions_provider_id_provider_configs
            FOREIGN KEY (provider_id) REFERENCES provider_configs(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE UNIQUE INDEX ux_provider_config_revisions_provider_revision
        ON provider_config_revisions(provider_id, revision)
        """,
        """
        CREATE TABLE provider_default_selection (
          id VARCHAR(16) PRIMARY KEY NOT NULL CHECK (id = 'default'),
          provider_id VARCHAR(36) NOT NULL,
          config_revision_id VARCHAR(36) NOT NULL,
          updated_at DATETIME NOT NULL,
          CONSTRAINT fk_provider_default_selection_provider_id_provider_configs
            FOREIGN KEY (provider_id) REFERENCES provider_configs(id) ON DELETE RESTRICT,
          CONSTRAINT fk_provider_default_selection_config_revision_id_provider_config_revisions
            FOREIGN KEY (config_revision_id) REFERENCES provider_config_revisions(id)
            ON DELETE RESTRICT
        )
        """,
        "PRAGMA legacy_alter_table=ON",
        _create_assets_table("assets_phase3", "'person', 'garment', 'generated_output'"),
        f"INSERT INTO assets_phase3 ({ASSET_COLUMNS}) SELECT {ASSET_COLUMNS} FROM assets",
        "DROP TABLE assets",
        "ALTER TABLE assets_phase3 RENAME TO assets",
        "PRAGMA legacy_alter_table=OFF",
        "CREATE INDEX ix_assets_list_order ON assets(created_at DESC, id DESC)",
        "CREATE INDEX ix_assets_kind_favorite ON assets(kind, favorite)",
        *_create_asset_triggers("", "assets"),
        """
        CREATE TABLE jobs (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          mode VARCHAR(32) NOT NULL CHECK (mode IN ('precise_try_on', 'unknown')),
          state VARCHAR(24) NOT NULL CHECK (
            state IN ('queued', 'waiting_provider', 'preparing', 'running',
              'needs_attention', 'succeeded', 'partially_succeeded', 'failed', 'cancelled')
          ),
          block_reason VARCHAR(32),
          blocked_detail VARCHAR(500),
          candidate_count INTEGER NOT NULL CHECK (
            candidate_count >= 1 AND candidate_count <= 4
          ),
          seed INTEGER,
          advanced_parameters_json TEXT NOT NULL DEFAULT '{}',
          garment_asset_id VARCHAR(36) NOT NULL,
          mask_asset_id VARCHAR(36),
          related_job_id VARCHAR(36),
          provider_id VARCHAR(36) NOT NULL,
          provider_revision_id VARCHAR(36) NOT NULL,
          provider_snapshot_json TEXT NOT NULL,
          workflow_version_id VARCHAR(36),
          workflow_snapshot_json TEXT,
          next_attempt_at DATETIME,
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          CONSTRAINT ck_jobs_block_reason CHECK (
            block_reason IS NULL OR block_reason IN (
          """ + BLOCK_REASONS + """
            )
          ),
          CONSTRAINT ck_jobs_workflow_pair CHECK (
            (workflow_version_id IS NULL AND workflow_snapshot_json IS NULL) OR
            workflow_version_id IS NOT NULL
          ),
          CONSTRAINT fk_jobs_garment_asset_id_assets
            FOREIGN KEY (garment_asset_id) REFERENCES assets(id) ON DELETE RESTRICT,
          CONSTRAINT fk_jobs_related_job_id_jobs
            FOREIGN KEY (related_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
          CONSTRAINT fk_jobs_provider_id_provider_configs
            FOREIGN KEY (provider_id) REFERENCES provider_configs(id) ON DELETE RESTRICT,
          CONSTRAINT fk_jobs_provider_revision_id_provider_config_revisions
            FOREIGN KEY (provider_revision_id) REFERENCES provider_config_revisions(id)
            ON DELETE RESTRICT
        )
        """,
        "CREATE INDEX ix_jobs_list_order ON jobs(created_at DESC, id DESC)",
        "CREATE INDEX ix_jobs_state ON jobs(state)",
        """
        CREATE TABLE job_person_inputs (
          job_id VARCHAR(36) NOT NULL,
          person_asset_id VARCHAR(36) NOT NULL,
          ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
          created_at DATETIME NOT NULL,
          PRIMARY KEY (job_id, person_asset_id),
          CONSTRAINT fk_job_person_inputs_job_id_jobs
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
          CONSTRAINT fk_job_person_inputs_person_asset_id_assets
            FOREIGN KEY (person_asset_id) REFERENCES assets(id) ON DELETE RESTRICT
        )
        """,
        """
        CREATE UNIQUE INDEX ux_job_person_inputs_ordinal
        ON job_person_inputs(job_id, ordinal)
        """,
        """
        CREATE TABLE job_items (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          job_id VARCHAR(36) NOT NULL,
          person_asset_id VARCHAR(36) NOT NULL,
          candidate_index INTEGER NOT NULL CHECK (candidate_index >= 0),
          attempt INTEGER NOT NULL CHECK (attempt >= 1),
          state VARCHAR(24) NOT NULL CHECK (
            state IN (
          """ + JOB_ITEM_STATES + """
            )
          ),
          block_reason VARCHAR(32),
          retry_of_job_item_id VARCHAR(36),
          superseded_by_job_item_id VARCHAR(36),
          external_execution_id VARCHAR(160),
          error_code VARCHAR(96),
          error_json TEXT,
          next_attempt_at DATETIME,
          transient_attempts INTEGER NOT NULL DEFAULT 0 CHECK (transient_attempts >= 0),
          claimant_token VARCHAR(64),
          claimed_at DATETIME,
          lease_expires_at DATETIME,
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          CONSTRAINT ck_job_items_block_reason CHECK (
            block_reason IS NULL OR block_reason IN (
          """ + BLOCK_REASONS + """
            )
          ),
          CONSTRAINT ck_job_items_claim CHECK (
            (claimant_token IS NULL AND claimed_at IS NULL AND lease_expires_at IS NULL) OR
            (claimant_token IS NOT NULL AND claimed_at IS NOT NULL AND
              lease_expires_at IS NOT NULL)
          ),
          CONSTRAINT ck_job_items_lease CHECK (
            lease_expires_at IS NULL OR lease_expires_at > claimed_at
          ),
          CONSTRAINT fk_job_items_job_id_jobs
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
          CONSTRAINT fk_job_items_person_asset_id_assets
            FOREIGN KEY (person_asset_id) REFERENCES assets(id) ON DELETE RESTRICT,
          CONSTRAINT fk_job_items_retry_of_job_item_id_job_items
            FOREIGN KEY (retry_of_job_item_id) REFERENCES job_items(id) ON DELETE SET NULL,
          CONSTRAINT fk_job_items_superseded_by_job_item_id_job_items
            FOREIGN KEY (superseded_by_job_item_id) REFERENCES job_items(id) ON DELETE SET NULL
        )
        """,
        "CREATE INDEX ix_job_items_job_candidate ON job_items(job_id, candidate_index)",
        """
        CREATE UNIQUE INDEX ux_job_items_candidate_attempt
        ON job_items(job_id, candidate_index, attempt)
        """,
        """
        CREATE INDEX ix_job_items_claim
        ON job_items(state, next_attempt_at, lease_expires_at)
        """,
        f"""
        CREATE UNIQUE INDEX ux_job_items_active_candidate
        ON job_items(job_id, candidate_index)
        WHERE state NOT IN {ACTIVE_ITEM_STATES}
        """,
        """
        CREATE UNIQUE INDEX ux_job_items_external_execution
        ON job_items(external_execution_id)
        WHERE external_execution_id IS NOT NULL
        """,
        """
        CREATE TABLE generated_outputs (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          job_item_id VARCHAR(36) NOT NULL,
          asset_id VARCHAR(36) NOT NULL,
          favorite BOOLEAN NOT NULL DEFAULT 0,
          seed INTEGER,
          actual_parameters_json TEXT NOT NULL DEFAULT '{}',
          quality_warnings_json TEXT NOT NULL DEFAULT '[]',
          created_at DATETIME NOT NULL,
          CONSTRAINT fk_generated_outputs_job_item_id_job_items
            FOREIGN KEY (job_item_id) REFERENCES job_items(id) ON DELETE CASCADE,
          CONSTRAINT fk_generated_outputs_asset_id_assets
            FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE RESTRICT
        )
        """,
        "CREATE INDEX ix_generated_outputs_item ON generated_outputs(job_item_id)",
        "CREATE INDEX ix_generated_outputs_asset ON generated_outputs(asset_id)",
        """
        CREATE UNIQUE INDEX ux_generated_outputs_item_asset
        ON generated_outputs(job_item_id, asset_id)
        """,
        """
        CREATE TABLE job_execution_events (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          job_id VARCHAR(36) NOT NULL,
          job_item_id VARCHAR(36),
          event_type VARCHAR(48) NOT NULL,
          from_state VARCHAR(24),
          to_state VARCHAR(24),
          error_code VARCHAR(96),
          detail_json TEXT NOT NULL DEFAULT '{}',
          occurred_at DATETIME NOT NULL,
          CONSTRAINT fk_job_execution_events_job_id_jobs
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
          CONSTRAINT fk_job_execution_events_job_item_id_job_items
            FOREIGN KEY (job_item_id) REFERENCES job_items(id) ON DELETE SET NULL
        )
        """,
        """
        CREATE INDEX ix_job_execution_events_job
        ON job_execution_events(job_id, occurred_at)
        """,
        """
        CREATE INDEX ix_job_execution_events_item
        ON job_execution_events(job_item_id, occurred_at)
        """,
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    for table in (
        "job_execution_events",
        "generated_outputs",
        "job_items",
        "job_person_inputs",
        "jobs",
    ):
        op.drop_table(table)

    _drop_asset_triggers()
    op.execute(
        "DELETE FROM asset_references WHERE asset_id IN "
        "(SELECT id FROM assets WHERE kind = 'generated_output')"
    )
    op.execute("DELETE FROM assets WHERE kind = 'generated_output'")
    op.execute("PRAGMA legacy_alter_table=ON")
    op.execute(_create_assets_table("assets_phase2", "'person', 'garment'"))
    op.execute(f"INSERT INTO assets_phase2 ({ASSET_COLUMNS}) SELECT {ASSET_COLUMNS} FROM assets")
    op.execute("DROP TABLE assets")
    op.execute("ALTER TABLE assets_phase2 RENAME TO assets")
    op.execute("PRAGMA legacy_alter_table=OFF")
    op.execute("CREATE INDEX ix_assets_list_order ON assets(created_at DESC, id DESC)")
    op.execute("CREATE INDEX ix_assets_kind_favorite ON assets(kind, favorite)")
    for statement in _create_asset_triggers("", "assets"):
        op.execute(statement)

    for table in (
        "provider_default_selection",
        "provider_config_revisions",
        "provider_configs",
    ):
        op.drop_table(table)
