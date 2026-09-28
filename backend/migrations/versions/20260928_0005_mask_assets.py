"""Enable private mask assets for related correction jobs.

Revision ID: 20260928_0005
Revises: 20260928_0004
Create Date: 2026-09-28
"""

from alembic import op

revision: str = "20260928_0005"
down_revision: str | None = "20260928_0004"
branch_labels: str | None = None
depends_on: str | None = None

ASSET_COLUMNS = (
    "id, kind, stored_object_id, favorite, content_state, created_at, updated_at, deleted_at"
)
UPLOAD_COLUMNS = (
    "id, actor_token_id, asset_kind, filename, content_type, expected_size, "
    "confirmed_offset, temp_name, state, garment_category, garment_source, client_sha256, "
    "completed_asset_id, error_code, created_at, updated_at, expires_at"
)


def _assets_table(name: str, kinds: str) -> str:
    return f"""
        CREATE TABLE {name} (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          kind VARCHAR(16) NOT NULL CHECK (kind IN ({kinds})),
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


def _upload_sessions_table(name: str, kinds: str, *, allow_mask: bool) -> str:
    mask_metadata = (
        " OR (asset_kind = 'mask' AND garment_category IS NULL AND garment_source IS NULL)"
        if allow_mask
        else ""
    )
    return f"""
        CREATE TABLE {name} (
          id VARCHAR(36) PRIMARY KEY NOT NULL,
          actor_token_id VARCHAR(36) NOT NULL,
          asset_kind VARCHAR(16) NOT NULL CHECK (asset_kind IN ({kinds})),
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
          CONSTRAINT uq_{name}_temp_name UNIQUE (temp_name),
          CONSTRAINT fk_{name}_actor_token_id_access_tokens
            FOREIGN KEY (actor_token_id) REFERENCES access_tokens(id) ON DELETE RESTRICT,
          CONSTRAINT fk_{name}_completed_asset_id_assets
            FOREIGN KEY (completed_asset_id) REFERENCES assets(id) ON DELETE SET NULL,
          CONSTRAINT ck_{name}_offset CHECK (
            confirmed_offset >= 0 AND confirmed_offset <= expected_size
          ),
          CONSTRAINT ck_{name}_expiry CHECK (expires_at > created_at),
          CONSTRAINT ck_{name}_subtype_metadata CHECK (
            (asset_kind = 'person' AND garment_category IS NULL AND garment_source IS NULL) OR
            (asset_kind = 'garment' AND garment_category IS NOT NULL AND garment_source IS NOT NULL)
            {mask_metadata}
          ),
          CONSTRAINT ck_{name}_completion CHECK (
            (state = 'completed' AND completed_asset_id IS NOT NULL) OR
            (state <> 'completed' AND completed_asset_id IS NULL)
          )
        )
    """


def _drop_asset_triggers() -> None:
    for trigger in (
        "stored_object_ref_after_asset_delete",
        "stored_object_ref_after_asset_update",
        "stored_object_ref_after_asset_insert",
        "ck_asset_kind_immutable",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")


def _create_asset_triggers() -> None:
    for statement in (
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
    ):
        op.execute(statement)


def _rebuild(*, allow_mask: bool) -> None:
    asset_kinds = "'person', 'garment', 'generated_output'"
    upload_kinds = "'person', 'garment'"
    if allow_mask:
        asset_kinds += ", 'mask'"
        upload_kinds += ", 'mask'"

    _drop_asset_triggers()
    op.execute("PRAGMA legacy_alter_table=ON")
    op.execute("ALTER TABLE assets RENAME TO assets_phase6_old")
    op.execute(_assets_table("assets", asset_kinds))
    op.execute(
        f"INSERT INTO assets ({ASSET_COLUMNS}) SELECT {ASSET_COLUMNS} FROM assets_phase6_old"
    )
    op.execute("DROP TABLE assets_phase6_old")
    op.execute("CREATE INDEX ix_assets_list_order ON assets(created_at DESC, id DESC)")
    op.execute("CREATE INDEX ix_assets_kind_favorite ON assets(kind, favorite)")
    _create_asset_triggers()

    op.execute("ALTER TABLE upload_sessions RENAME TO upload_sessions_phase6_old")
    op.execute(_upload_sessions_table("upload_sessions", upload_kinds, allow_mask=allow_mask))
    op.execute(
        f"INSERT INTO upload_sessions ({UPLOAD_COLUMNS}) "
        f"SELECT {UPLOAD_COLUMNS} FROM upload_sessions_phase6_old"
    )
    op.execute("DROP TABLE upload_sessions_phase6_old")
    op.execute(
        "CREATE INDEX ix_upload_sessions_actor_state ON upload_sessions(actor_token_id, state)"
    )
    op.execute("CREATE INDEX ix_upload_sessions_expiry ON upload_sessions(expires_at)")
    op.execute("PRAGMA legacy_alter_table=OFF")


def _set_foreign_keys(enabled: bool) -> None:
    # SQLite ignores this PRAGMA inside a transaction. Alembic's autocommit block
    # makes the table rebuild explicit and prevents dependent FKs being rewritten
    # to the temporary table names.
    with op.get_context().autocommit_block():
        op.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def upgrade() -> None:
    _set_foreign_keys(False)
    _rebuild(allow_mask=True)
    _set_foreign_keys(True)


def downgrade() -> None:
    bind = op.get_bind()
    mask_assets = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM assets WHERE kind = 'mask'"
    ).scalar_one()
    mask_uploads = bind.exec_driver_sql(
        "SELECT COUNT(*) FROM upload_sessions WHERE asset_kind = 'mask'"
    ).scalar_one()
    if mask_assets or mask_uploads:
        raise RuntimeError("cannot downgrade while mask assets or uploads exist")
    _set_foreign_keys(False)
    _rebuild(allow_mask=False)
    _set_foreign_keys(True)
