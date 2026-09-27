"""Single-owner reconciliation for resumable upload temporary files."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clothes_model.infrastructure.database import models as db
from clothes_model.infrastructure.storage.local import LocalFileStorage


async def reconcile_upload_sessions(
    sessions: async_sessionmaker[AsyncSession], storage: LocalFileStorage
) -> None:
    """Expire abandoned uploads and truncate bytes beyond the committed offset."""
    now = datetime.now(UTC)
    async with sessions() as session:
        try:
            rows = (
                (
                    await session.execute(
                        select(db.upload_sessions).where(
                            db.upload_sessions.c.state.in_(("created", "uploading"))
                        )
                    )
                )
                .mappings()
                .all()
            )
        except OperationalError:
            await session.rollback()
            return
        for row in rows:
            name = str(row["temp_name"])
            if Path(name).name != name or not name.endswith(".part"):
                continue
            path = storage.temp / name
            if row["expires_at"] <= now:
                await session.execute(
                    update(db.upload_sessions)
                    .where(db.upload_sessions.c.id == row["id"])
                    .values(state="cancelled", updated_at=now)
                )
                path.unlink(missing_ok=True)
                continue
            if path.is_file() and path.stat().st_size > row["confirmed_offset"]:
                with path.open("r+b") as handle:
                    handle.truncate(row["confirmed_offset"])
        await session.commit()
