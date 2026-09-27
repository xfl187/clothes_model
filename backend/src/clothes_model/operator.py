"""Operator-only security commands for first deploy and credential recovery."""

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from clothes_model.core.config import get_settings
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.modules.auth.application import TokenService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clothes-model-security")
    parser.add_argument("--database-url", help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap", help="create missing App/Admin credentials")
    commands.add_parser("reset-admin", help="revoke Admin lineage and issue a replacement")
    commands.add_parser("rotate-app", help="revoke active App credentials and issue a replacement")
    return parser


async def _execute(command: str, database_url: str) -> list[str]:
    runtime = create_database_runtime(database_url, get_settings().sqlite_busy_timeout_ms)
    try:
        service = TokenService(lambda: SqlAlchemyUnitOfWork(runtime.sessions))
        if command == "bootstrap":
            issued = await service.bootstrap()
            if not issued:
                return ["Active App/Admin credentials already exist; no credential was displayed."]
            return [
                f"Created {credential.scope.title()} Token (shown once): {credential.value}"
                for credential in issued
            ]
        if command == "reset-admin":
            credential = await service.reset_admin()
            return [f"Created Admin Token (shown once): {credential.value}"]
        credential = await service.rotate_app()
        return [f"Created App Token (shown once): {credential.value}"]
    finally:
        await runtime.close()


def run(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    settings = get_settings()
    database_url = arguments.database_url or settings.database_url
    lock_path = settings.instance_lock_path.with_suffix(".security-migration.lock")
    if database_url.startswith("sqlite+aiosqlite:///"):
        database_path = Path(database_url.removeprefix("sqlite+aiosqlite:///"))
        if database_path.parent != Path(""):
            database_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    upgrade_database(database_url, lock_path)
    for line in asyncio.run(_execute(arguments.command, database_url)):
        print(line)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
