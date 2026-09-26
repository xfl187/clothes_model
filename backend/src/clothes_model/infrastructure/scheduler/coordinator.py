"""Single-instance scheduler ownership coordinator."""

from pathlib import Path

from clothes_model.infrastructure.locking import AdvisoryFileLock, LockUnavailableError
from clothes_model.infrastructure.scheduler.ports import SchedulerLifecycle


class InstanceOwnershipError(RuntimeError):
    """Safe startup failure when another scheduler instance owns the lock."""


class SchedulerCoordinator:
    def __init__(
        self,
        *,
        enabled: bool,
        lock_path: Path,
        scheduler: SchedulerLifecycle,
    ) -> None:
        self._enabled = enabled
        self._lock = AdvisoryFileLock(lock_path)
        self._scheduler = scheduler
        self._status = "not_started"

    @property
    def status(self) -> str:
        return self._status

    async def start(self) -> None:
        if not self._enabled:
            self._status = "disabled"
            return
        try:
            self._lock.acquire()
        except LockUnavailableError as error:
            self._status = "ownership_unavailable"
            raise InstanceOwnershipError(
                "scheduler ownership is already held by another instance"
            ) from error
        try:
            await self._scheduler.start()
        except BaseException:
            self._lock.release()
            self._status = "start_failed"
            raise
        self._status = "owned"

    async def stop(self) -> None:
        try:
            if self._scheduler.running:
                await self._scheduler.stop()
        finally:
            self._lock.release()
            self._status = "stopped"
