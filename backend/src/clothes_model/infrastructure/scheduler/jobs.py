"""Single-instance polling scheduler that claims and executes durable job items."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clothes_model.core.logging import get_logger
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.infrastructure.database import models as db
from clothes_model.modules.jobs.infrastructure.execution import JobExecutionService

logger = get_logger(__name__)

CLAIMABLE_STATES = ("queued", "waiting_provider")


async def reconcile_claims(
    sessions: async_sessionmaker[AsyncSession], now: datetime
) -> None:
    """Recover safe work and stop uncertain prior-running work after a restart."""
    async with SqlAlchemyUnitOfWork(sessions) as uow:
        # A crashed pre-submission preparation is safe to try again.
        await uow.session.execute(
            update(db.job_items)
            .where(
                db.job_items.c.state == "preparing",
                db.job_items.c.lease_expires_at.is_not(None),
                db.job_items.c.lease_expires_at < now,
            )
            .values(state="queued", claimant_token=None, claimed_at=None, lease_expires_at=None)
        )
        # A previously running item with an expired lease is uncertain, never blindly rerun.
        await uow.session.execute(
            update(db.job_items)
            .where(
                db.job_items.c.state == "running",
                db.job_items.c.lease_expires_at.is_not(None),
                db.job_items.c.lease_expires_at < now,
            )
            .values(
                state="needs_attention",
                block_reason="external_state_unknown",
                claimant_token=None,
                claimed_at=None,
                lease_expires_at=None,
            )
        )
        # Release any other stale claim so it can be re-claimed deterministically.
        await uow.session.execute(
            update(db.job_items)
            .where(
                db.job_items.c.claimant_token.is_not(None),
                db.job_items.c.lease_expires_at < now,
            )
            .values(claimant_token=None, claimed_at=None, lease_expires_at=None)
        )
        await uow.commit()


class JobScheduler:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        execution: JobExecutionService,
        *,
        poll_interval_seconds: float = 0.5,
        batch_size: int = 1,
        lease_minutes: int = 5,
        claimant_token: str | None = None,
        clock: Callable[[], datetime] | None = None,
        capacity: Callable[[], bool] | None = None,
    ) -> None:
        self._sessions = sessions
        self._execution = execution
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._lease = timedelta(minutes=lease_minutes)
        self._claimant_token = claimant_token or str(uuid4())
        self._clock = clock or (lambda: datetime.now(UTC))
        self._capacity = capacity or (lambda: True)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self.claimed_total = 0

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        await reconcile_claims(self._sessions, self._clock())
        await self._execution.reconcile_external()
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="job-scheduler")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except Exception:
                logger.exception("scheduler_tick_failed")
            await asyncio.sleep(self._poll_interval)

    async def tick(self) -> int:
        now = self._clock()
        if not self._capacity():
            # Already-persisted work stays queued and resumes automatically when space
            # returns; it is never failed and no external execution is started.
            async with SqlAlchemyUnitOfWork(self._sessions) as uow:
                await uow.session.execute(
                    update(db.job_items)
                    .where(
                        db.job_items.c.state.in_(list(CLAIMABLE_STATES)),
                        db.job_items.c.claimant_token.is_(None),
                    )
                    .values(block_reason="storage_capacity", updated_at=now)
                )
                await uow.commit()
            return 0
        async with SqlAlchemyUnitOfWork(self._sessions) as uow:
            claimable = await uow.jobs.list_claimable_item_ids(
                now=now, states=CLAIMABLE_STATES, limit=self._batch_size
            )
        executed = 0
        for item_id in claimable:
            if await self._claim(item_id, now):
                self.claimed_total += 1
                await self._execution.execute(item_id, self._claimant_token)
                executed += 1
        return executed

    async def _claim(self, item_id: str, now: datetime) -> bool:
        async with SqlAlchemyUnitOfWork(self._sessions) as uow:
            claimed = await uow.jobs.claim_item(
                item_id,
                claimant_token=self._claimant_token,
                claimed_at=now,
                lease_expires_at=now + self._lease,
            )
            await uow.commit()
        return claimed


__all__ = ["CLAIMABLE_STATES", "JobScheduler", "reconcile_claims"]
