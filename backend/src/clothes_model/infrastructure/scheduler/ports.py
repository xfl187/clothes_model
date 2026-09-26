"""Scheduler lifecycle ports without business job behavior."""

from typing import Protocol


class JobSource(Protocol):
    async def next_job_ids(self) -> tuple[str, ...]: ...


class SchedulerLifecycle(Protocol):
    @property
    def running(self) -> bool: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...
