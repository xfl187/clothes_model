"""Serial production migration entrypoint."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from clothes_model.core.config import get_settings
from clothes_model.infrastructure.locking import AdvisoryFileLock


def alembic_config(database_url: str) -> Config:
    candidates = (Path.cwd() / "alembic.ini", Path(__file__).parents[4] / "alembic.ini")
    config_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if config_path is None:
        raise FileNotFoundError("alembic.ini was not found in the runtime or source layout")
    config = Config(str(config_path))
    config.attributes["database_url"] = database_url
    return config


def upgrade_database(database_url: str, lock_path: Path, revision: str = "head") -> None:
    """Upgrade under an advisory lock so migrations are serialized per host."""
    with AdvisoryFileLock(lock_path):
        command.upgrade(alembic_config(database_url), revision)


def main() -> None:
    settings = get_settings()
    migration_lock = settings.instance_lock_path.with_suffix(".migration.lock")
    upgrade_database(settings.database_url, migration_lock)


if __name__ == "__main__":
    main()
