"""Add Comfy node and immutable Workflow persistence.

Revision ID: 20260928_0004
Revises: 20260927_0003
Create Date: 2026-09-28
"""

from alembic import op
from sqlalchemy import text

revision: str = "20260928_0004"
down_revision: str | None = "20260927_0003"
branch_labels: str | None = None
depends_on: str | None = None

LOGICAL_PROVIDER_ID = "00000000-0000-4000-8000-000000000005"
LOGICAL_REVISION_ID = "00000000-0000-4000-8000-000000000006"


def _jobs_table(name: str, *, workflow_fk: bool) -> str:
    workflow_constraint = ""
    if workflow_fk:
        workflow_constraint = f""",
          CONSTRAINT fk_{name}_workflow_version_id_workflow_versions
            FOREIGN KEY (workflow_version_id) REFERENCES workflow_versions(id)
            ON DELETE RESTRICT"""
    return f"""
        CREATE TABLE {name} (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          mode VARCHAR(32) NOT NULL CHECK (mode IN ('precise_try_on', 'unknown')),
          state VARCHAR(24) NOT NULL CHECK (
            state IN ('queued', 'waiting_provider', 'preparing', 'running',
              'needs_attention', 'succeeded', 'partially_succeeded', 'failed', 'cancelled')
          ),
          block_reason VARCHAR(32) CHECK (
            block_reason IS NULL OR block_reason IN (
              'provider_offline', 'storage_capacity', 'retry_backoff',
              'locked_configuration_unavailable', 'external_state_unknown',
              'configuration_invalid', 'unknown'
            )
          ),
          blocked_detail VARCHAR(500),
          candidate_count INTEGER NOT NULL CHECK (candidate_count >= 1 AND candidate_count <= 4),
          seed INTEGER,
          advanced_parameters_json TEXT NOT NULL DEFAULT '{{}}',
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
          CONSTRAINT ck_{name}_workflow_pair CHECK (
            (workflow_version_id IS NULL AND workflow_snapshot_json IS NULL) OR
            workflow_version_id IS NOT NULL
          ),
          CONSTRAINT fk_{name}_garment_asset_id_assets
            FOREIGN KEY (garment_asset_id) REFERENCES assets(id) ON DELETE RESTRICT,
          CONSTRAINT fk_{name}_related_job_id_jobs
            FOREIGN KEY (related_job_id) REFERENCES {name}(id) ON DELETE SET NULL,
          CONSTRAINT fk_{name}_provider_id_provider_configs
            FOREIGN KEY (provider_id) REFERENCES provider_configs(id) ON DELETE RESTRICT,
          CONSTRAINT fk_{name}_provider_revision_id_provider_config_revisions
            FOREIGN KEY (provider_revision_id) REFERENCES provider_config_revisions(id)
            ON DELETE RESTRICT
          {workflow_constraint}
        )
    """


def _rebuild_jobs(*, workflow_fk: bool) -> None:
    target = "jobs_phase5" if workflow_fk else "jobs_phase3"
    op.execute("PRAGMA legacy_alter_table=ON")
    op.execute(f"ALTER TABLE jobs RENAME TO {target}_old")
    op.execute(_jobs_table("jobs", workflow_fk=workflow_fk))
    columns = (
        "id, mode, state, block_reason, blocked_detail, candidate_count, seed, "
        "advanced_parameters_json, garment_asset_id, mask_asset_id, related_job_id, "
        "provider_id, provider_revision_id, provider_snapshot_json, workflow_version_id, "
        "workflow_snapshot_json, next_attempt_at, created_at, updated_at"
    )
    op.execute(f"INSERT INTO jobs ({columns}) SELECT {columns} FROM {target}_old")
    op.execute(f"DROP TABLE {target}_old")
    op.execute("PRAGMA legacy_alter_table=OFF")
    op.execute("CREATE INDEX ix_jobs_list_order ON jobs(created_at DESC, id DESC)")
    op.execute("CREATE INDEX ix_jobs_state ON jobs(state)")


def upgrade() -> None:
    statements = (
        """
        CREATE TABLE comfy_node_config (
          id VARCHAR(16) PRIMARY KEY NOT NULL CHECK (id = 'default'),
          endpoint VARCHAR(512) NOT NULL,
          credential_envelope TEXT,
          credential_updated_at DATETIME,
          timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds >= 1 AND timeout_seconds <= 3600),
          enabled BOOLEAN NOT NULL DEFAULT 0,
          health_status VARCHAR(16) NOT NULL DEFAULT 'unchecked' CHECK (
            health_status IN ('unchecked', 'healthy', 'offline', 'incompatible')
          ),
          health_detail VARCHAR(500),
          observed_server_version VARCHAR(160),
          observed_capabilities_json TEXT NOT NULL DEFAULT '{}',
          last_checked_at DATETIME,
          created_at DATETIME NOT NULL,
          updated_at DATETIME NOT NULL,
          CONSTRAINT ck_comfy_node_config_credential_pair CHECK (
            (credential_envelope IS NULL AND credential_updated_at IS NULL) OR
            (credential_envelope IS NOT NULL AND credential_updated_at IS NOT NULL)
          )
        )
        """,
        """
        CREATE TABLE workflow_versions (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          workflow_id VARCHAR(36) NOT NULL,
          version INTEGER NOT NULL CHECK (version >= 1),
          mode VARCHAR(32) NOT NULL CHECK (mode IN ('precise_try_on', 'unknown')),
          display_name VARCHAR(160) NOT NULL,
          state VARCHAR(16) NOT NULL CHECK (state IN ('draft', 'active', 'retired')),
          workflow_sha256 VARCHAR(64) NOT NULL CHECK (length(workflow_sha256) = 64),
          workflow_path TEXT NOT NULL,
          manifest_sha256 VARCHAR(64) NOT NULL CHECK (length(manifest_sha256) = 64),
          manifest_path TEXT NOT NULL,
          bindings_schema_version VARCHAR(32) NOT NULL,
          manifest_json TEXT NOT NULL,
          capabilities_json TEXT NOT NULL,
          validation_json TEXT,
          validated_at DATETIME,
          activated_at DATETIME,
          retired_at DATETIME,
          created_at DATETIME NOT NULL,
          CONSTRAINT uq_workflow_versions_identity UNIQUE (workflow_id, version),
          CONSTRAINT ck_workflow_versions_lifecycle CHECK (
            (state = 'draft' AND activated_at IS NULL AND retired_at IS NULL) OR
            (state = 'active' AND validated_at IS NOT NULL AND activated_at IS NOT NULL
              AND retired_at IS NULL) OR
            (state = 'retired' AND validated_at IS NOT NULL AND activated_at IS NOT NULL
              AND retired_at IS NOT NULL)
          )
        )
        """,
        "CREATE INDEX ix_workflow_versions_workflow ON workflow_versions(workflow_id, version)",
        """
        CREATE UNIQUE INDEX ux_workflow_versions_artifact_identity
        ON workflow_versions(workflow_sha256, manifest_sha256)
        """,
        """
        CREATE UNIQUE INDEX ux_workflow_versions_active_mode
        ON workflow_versions(mode) WHERE state = 'active'
        """,
        """
        CREATE TABLE workflow_validation_runs (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          workflow_version_id VARCHAR(36) NOT NULL,
          status VARCHAR(16) NOT NULL CHECK (
            status IN ('passed', 'failed', 'offline', 'incompatible')
          ),
          result_json TEXT NOT NULL,
          checked_node_fingerprint VARCHAR(128),
          created_at DATETIME NOT NULL,
          CONSTRAINT fk_workflow_validation_runs_workflow_version_id_workflow_versions
            FOREIGN KEY (workflow_version_id) REFERENCES workflow_versions(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX ix_workflow_validation_runs_version
        ON workflow_validation_runs(workflow_version_id, created_at)
        """,
        """
        CREATE TRIGGER ck_workflow_artifact_identity_immutable
        BEFORE UPDATE OF workflow_id, version, mode, workflow_sha256, workflow_path,
          manifest_sha256, manifest_path, bindings_schema_version, manifest_json,
          capabilities_json, created_at ON workflow_versions
        BEGIN
          SELECT RAISE(ABORT, 'workflow artifact identity is immutable');
        END
        """,
    )
    for statement in statements:
        op.execute(statement)

    _rebuild_jobs(workflow_fk=True)

    op.execute(
        f"""
        INSERT OR IGNORE INTO provider_configs (
          id, display_name, provider_type, state, created_at, updated_at
        ) VALUES (
          '{LOGICAL_PROVIDER_ID}', 'ComfyUI', 'comfyui', 'inactive', CURRENT_TIMESTAMP,
          CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        text(
            f"""
        INSERT OR IGNORE INTO provider_config_revisions (
          id, provider_id, revision, adapter_type, endpoint, model, timeout_seconds,
          vendor_parameters_json, capabilities_json, created_at
        ) VALUES (
          '{LOGICAL_REVISION_ID}', '{LOGICAL_PROVIDER_ID}', 1, 'comfyui',
          'comfy://physical-node', 'workflow', 300, '{{}}', :capabilities, CURRENT_TIMESTAMP
        )
        """
        ).bindparams(
            capabilities='{"modes":["precise_try_on"],"workflow_required":true}'
        )
    )


def downgrade() -> None:
    _rebuild_jobs(workflow_fk=False)
    op.execute("DROP TRIGGER IF EXISTS ck_workflow_artifact_identity_immutable")
    op.drop_table("workflow_validation_runs")
    op.drop_table("workflow_versions")
    op.drop_table("comfy_node_config")
    op.execute(
        f"DELETE FROM provider_config_revisions WHERE id = '{LOGICAL_REVISION_ID}'"
    )
    op.execute(f"DELETE FROM provider_configs WHERE id = '{LOGICAL_PROVIDER_ID}'")
