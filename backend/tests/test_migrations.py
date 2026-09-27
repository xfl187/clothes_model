import sqlite3
from pathlib import Path

import pytest
from alembic import command

from clothes_model.infrastructure.database.migrations import alembic_config, upgrade_database

BASELINE_REVISION = "20260924_0001"
PHASE_2_REVISION = "20260926_0002"
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


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def current_revision(database_path: Path) -> str | None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return None if row is None else str(row[0])


def test_empty_database_upgrade_is_repeatable_and_reversible(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    database_url = sqlite_url(database_path)
    lock_path = tmp_path / "migration.lock"

    upgrade_database(database_url, lock_path)
    upgrade_database(database_url, lock_path)
    assert current_revision(database_path) == PHASE_2_REVISION

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }
    assert tables == PHASE_2_TABLES

    config = alembic_config(database_url)
    command.downgrade(config, BASELINE_REVISION)
    assert current_revision(database_path) == BASELINE_REVISION
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }
    assert tables == {"alembic_version"}

    command.upgrade(config, "head")
    assert current_revision(database_path) == PHASE_2_REVISION


def test_phase_1_database_upgrades_to_phase_2_and_has_no_future_tables(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "from-phase-1.db"
    config = alembic_config(sqlite_url(database_path))

    command.upgrade(config, BASELINE_REVISION)
    assert current_revision(database_path) == BASELINE_REVISION
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }

    assert current_revision(database_path) == PHASE_2_REVISION
    assert tables == PHASE_2_TABLES
    assert not tables & {"jobs", "job_items", "outputs", "providers", "workflows", "outfits"}
    command.check(config)


def test_alembic_config_uses_runtime_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_config = Path(__file__).parents[1] / "alembic.ini"
    runtime_config = tmp_path / "alembic.ini"
    runtime_config.write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = alembic_config("sqlite+aiosqlite:///runtime.db")

    assert Path(config.config_file_name or "") == runtime_config
