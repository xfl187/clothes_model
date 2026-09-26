"""No-op runtime components for the Phase 1 scheduler boundary."""

from clothes_model.infrastructure.scheduler.ports import JobSource


class NoOpJobSource:
    async def next_job_ids(self) -> tuple[str, ...]:
        return ()


class NoOpScheduler:
    """Own lifecycle state but never poll or execute business work."""

    def __init__(self, job_source: JobSource) -> None:
        self._job_source = job_source
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
