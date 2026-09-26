import sqlite3
from pathlib import Path

import pytest
from alembic import command

from clothes_model.infrastructure.database.migrations import alembic_config, upgrade_database


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
    assert current_revision(database_path) == "20260924_0001"

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }
    assert tables == {"alembic_version"}

    config = alembic_config(database_url)
    command.downgrade(config, "base")
    assert current_revision(database_path) is None
    command.upgrade(config, "head")
    assert current_revision(database_path) == "20260924_0001"

def test_alembic_config_uses_runtime_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_config = Path(__file__).parents[1] / "alembic.ini"
    runtime_config = tmp_path / "alembic.ini"
    runtime_config.write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = alembic_config("sqlite+aiosqlite:///runtime.db")

    assert Path(config.config_file_name or "") == runtime_config
