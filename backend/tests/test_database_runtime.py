import asyncio
from pathlib import Path

from sqlalchemy import text

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime


def sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def test_sqlite_pragmas_and_unit_of_work_boundaries(tmp_path: Path) -> None:
    async def exercise() -> None:
        runtime = create_database_runtime(sqlite_url(tmp_path / "runtime.db"), 3210)
        try:
            async with runtime.engine.begin() as connection:
                foreign_keys = await connection.exec_driver_sql("PRAGMA foreign_keys")
                journal_mode = await connection.exec_driver_sql("PRAGMA journal_mode")
                busy_timeout = await connection.exec_driver_sql("PRAGMA busy_timeout")
                await connection.execute(text("CREATE TABLE uow_probe (value INTEGER NOT NULL)"))

            assert foreign_keys.scalar_one() == 1
            assert journal_mode.scalar_one() == "wal"
            assert busy_timeout.scalar_one() == 3210

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(text("INSERT INTO uow_probe VALUES (1)"))

            async with runtime.engine.connect() as connection:
                rolled_back = await connection.scalar(text("SELECT COUNT(*) FROM uow_probe"))
            assert rolled_back == 0

            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.session.execute(text("INSERT INTO uow_probe VALUES (2)"))
                await uow.commit()

            async with runtime.engine.connect() as connection:
                committed = await connection.scalar(text("SELECT COUNT(*) FROM uow_probe"))
            assert committed == 1
        finally:
            await runtime.close()

    asyncio.run(exercise())


def test_database_runtime_rejects_non_sqlite_v1_url() -> None:
    try:
        create_database_runtime("postgresql+asyncpg://localhost/example", 5000)
    except ValueError as error:
        assert "sqlite+aiosqlite" in str(error)
    else:
        raise AssertionError("V1 must reject non-SQLite database URLs")
