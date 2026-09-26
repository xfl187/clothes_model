"""Async SQLAlchemy engine and session construction."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@dataclass(frozen=True, slots=True)
class DatabaseRuntime:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    async def close(self) -> None:
        await self.engine.dispose()


def create_database_runtime(database_url: str, busy_timeout_ms: int) -> DatabaseRuntime:
    if not database_url.startswith("sqlite+aiosqlite:"):
        raise ValueError("V1 database_url must use the sqlite+aiosqlite dialect")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    _install_sqlite_pragmas(engine, busy_timeout_ms)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return DatabaseRuntime(engine=engine, sessions=sessions)


def _install_sqlite_pragmas(engine: AsyncEngine, busy_timeout_ms: int) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms:d}")
        finally:
            cursor.close()
