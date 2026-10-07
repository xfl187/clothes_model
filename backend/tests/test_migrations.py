import sqlite3
from pathlib import Path

import pytest
from alembic import command

from clothes_model.infrastructure.database.migrations import alembic_config, upgrade_database

BASELINE_REVISION = "20260924_0001"
PHASE_2_REVISION = "20260926_0002"
PHASE_3_REVISION = "20260927_0003"
PHASE_5_REVISION = "20260928_0004"
PHASE_6_MASK_REVISION = "20260928_0005"
LOCAL_FIRST_REVISION = "20260929_0006"
PHASE_7_REVISION = "20261007_0007"
PHASE_9_REVISION = "20261007_0008"
PHASE_2_TABLES = {
    "access_tokens",
    "admin_sessions",
    "alembic_version",
    "asset_references",
    "assets",
    "auth_throttle_state",
    "garment_assets",
    "idempotency_records",
    "person_assets",
    "security_audit_events",
    "stored_objects",
    "upload_sessions",
}
PHASE_3_TABLES = PHASE_2_TABLES | {
    "generated_outputs",
    "job_execution_events",
    "job_items",
    "job_person_inputs",
    "jobs",
    "provider_config_revisions",
    "provider_configs",
    "provider_default_selection",
}
PHASE_5_TABLES = PHASE_3_TABLES | {
    "comfy_node_config",
    "workflow_validation_runs",
    "workflow_versions",
}
LOCAL_FIRST_TABLES = PHASE_5_TABLES | {"owner_scopes", "server_identity"}
PHASE_7_TABLES = LOCAL_FIRST_TABLES | {"retention_policy", "storage_scans"}
PHASE_9_TABLES = PHASE_7_TABLES | {
    "layer_type_definitions",
    "outfit_sessions",
    "outfit_branches",
    "outfit_revisions",
    "outfit_layers",
}


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def current_revision(database_path: Path) -> str | None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else str(row[0])


def table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }


def test_empty_database_upgrade_is_repeatable_and_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    database_url = sqlite_url(database_path)
    lock_path = tmp_path / "migration.lock"

    upgrade_database(database_url, lock_path)
    upgrade_database(database_url, lock_path)
    assert current_revision(database_path) == PHASE_9_REVISION
    assert table_names(database_path) == PHASE_9_TABLES

    config = alembic_config(database_url)
    command.downgrade(config, PHASE_3_REVISION)
    assert current_revision(database_path) == PHASE_3_REVISION
    assert table_names(database_path) == PHASE_3_TABLES

    command.upgrade(config, "head")
    assert current_revision(database_path) == PHASE_9_REVISION
    assert table_names(database_path) == PHASE_9_TABLES


def test_phase_2_database_upgrades_to_phase_3_and_has_no_future_tables(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "from-phase-2.db"
    config = alembic_config(sqlite_url(database_path))

    command.upgrade(config, PHASE_2_REVISION)
    assert current_revision(database_path) == PHASE_2_REVISION
    command.upgrade(config, "head")

    assert current_revision(database_path) == PHASE_9_REVISION
    tables = table_names(database_path)
    assert tables == PHASE_9_TABLES
    assert {
        "outfit_sessions",
        "outfit_branches",
        "outfit_revisions",
        "outfit_layers",
        "layer_type_definitions",
    } <= tables
    command.check(config)


def test_phase_3_upgrade_preserves_phase_2_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "preserve.db"
    config = alembic_config(sqlite_url(database_path))
    command.upgrade(config, PHASE_2_REVISION)

    timestamp = "2026-09-26 12:00:00.000000"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO stored_objects (id, sha256, relative_path, content_type, "
            "size_bytes, width, height, state, asset_ref_count, created_at) "
            "VALUES ('object-1', ?, 'objects/aa/object-1', 'image/jpeg', 128, 16, 8, "
            "'available', 0, ?)",
            ("a" * 64, timestamp),
        )
        connection.execute(
            "INSERT INTO assets (id, kind, stored_object_id, favorite, content_state, "
            "created_at, updated_at) VALUES ('asset-1', 'person', 'object-1', 0, "
            "'available', ?, ?)",
            (timestamp, timestamp),
        )
        connection.execute("INSERT INTO person_assets (asset_id) VALUES ('asset-1')")
        connection.execute(
            "INSERT INTO access_tokens (id, public_id, secret_hash, scope, status, "
            "created_at) VALUES ('token-1', 'public-1', 'hash', 'app', 'active', ?)",
            (timestamp,),
        )
        connection.execute(
            "INSERT INTO asset_references (id, asset_id, source_kind, source_id, "
            "active, created_at) VALUES ('reference-1', 'asset-1', 'job', 'job-1', 1, ?)",
            (timestamp,),
        )
        connection.commit()

    command.upgrade(config, "head")
    assert current_revision(database_path) == PHASE_9_REVISION

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        counts = {
            "stored_objects": connection.execute("SELECT COUNT(*) FROM stored_objects").fetchone()[
                0
            ],
            "assets": connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0],
            "person_assets": connection.execute("SELECT COUNT(*) FROM person_assets").fetchone()[0],
            "access_tokens": connection.execute("SELECT COUNT(*) FROM access_tokens").fetchone()[0],
            "asset_references": connection.execute(
                "SELECT COUNT(*) FROM asset_references"
            ).fetchone()[0],
        }
        ref_count = connection.execute(
            "SELECT asset_ref_count FROM stored_objects WHERE id = 'object-1'"
        ).fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert counts == {
        "stored_objects": 1,
        "assets": 1,
        "person_assets": 1,
        "access_tokens": 1,
        "asset_references": 1,
    }
    assert ref_count == 1
    assert violations == []


def test_phase_5_upgrade_and_downgrade_preserve_phase_3_job_and_default(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "preserve-phase3.db"
    config = alembic_config(sqlite_url(database_path))
    command.upgrade(config, PHASE_3_REVISION)
    timestamp = "2026-09-27 12:00:00.000000"

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO stored_objects (id, sha256, relative_path, content_type, "
            "size_bytes, width, height, state, asset_ref_count, created_at) VALUES "
            "('garment-object', ?, 'objects/aa/garment', 'image/jpeg', 128, 16, 8, "
            "'available', 0, ?)",
            ("a" * 64, timestamp),
        )
        connection.execute(
            "INSERT INTO assets (id, kind, stored_object_id, favorite, content_state, "
            "created_at, updated_at) VALUES ('garment-asset', 'garment', "
            "'garment-object', 0, 'available', ?, ?)",
            (timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO garment_assets (asset_id, category, source) VALUES "
            "('garment-asset', 'upper_body', 'photo')"
        )
        connection.execute(
            "INSERT INTO provider_configs (id, display_name, provider_type, state, "
            "created_at, updated_at) VALUES ('ark-provider', 'Ark', 'llm_image_edit', "
            "'active', ?, ?)",
            (timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO provider_config_revisions (id, provider_id, revision, adapter_type, "
            "endpoint, model, timeout_seconds, vendor_parameters_json, capabilities_json, "
            "created_at) VALUES ('ark-revision', 'ark-provider', 1, 'volcengine_ark_seedream', "
            "'https://ark.example/v1', 'seedream', 120, '{}', '{}', ?)",
            (timestamp,),
        )
        connection.execute(
            "INSERT INTO provider_default_selection (id, provider_id, config_revision_id, "
            "updated_at) VALUES ('default', 'ark-provider', 'ark-revision', ?)",
            (timestamp,),
        )
        connection.execute(
            "INSERT INTO jobs (id, mode, state, candidate_count, advanced_parameters_json, "
            "garment_asset_id, provider_id, provider_revision_id, provider_snapshot_json, "
            "created_at, updated_at) VALUES ('job-1', 'precise_try_on', 'queued', 1, '{}', "
            "'garment-asset', 'ark-provider', 'ark-revision', '{}', ?, ?)",
            (timestamp, timestamp),
        )
        connection.commit()

    command.upgrade(config, "head")
    command.downgrade(config, PHASE_3_REVISION)
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        job = connection.execute(
            "SELECT provider_id, provider_revision_id, workflow_version_id FROM jobs "
            "WHERE id = 'job-1'"
        ).fetchone()
        selected = connection.execute(
            "SELECT provider_id, config_revision_id FROM provider_default_selection "
            "WHERE id = 'default'"
        ).fetchone()
        ark_count = connection.execute(
            "SELECT COUNT(*) FROM provider_configs WHERE id = 'ark-provider'"
        ).fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert job == ("ark-provider", "ark-revision", None)
    assert selected == ("ark-provider", "ark-revision")
    assert ark_count == 1
    assert violations == []


def test_alembic_config_uses_runtime_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_config = Path(__file__).parents[1] / "alembic.ini"
    runtime_config = tmp_path / "alembic.ini"
    runtime_config.write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = alembic_config("sqlite+aiosqlite:///runtime.db")

    assert Path(config.config_file_name or "") == runtime_config
