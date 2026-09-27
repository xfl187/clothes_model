"""Persistence ports for durable jobs, outputs, and execution events."""

from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.jobs.domain import (
    GeneratedOutputRecord,
    Job,
    JobExecutionEvent,
    JobItem,
    JobPersonInput,
)


class JobRepository(Protocol):
    async def add_job(self, job: Job) -> None: ...

    async def get_job(self, job_id: str) -> Job | None: ...

    async def list_jobs(self, *, state: str | None = None, limit: int = 50) -> list[Job]: ...

    async def update_job(self, job: Job) -> None: ...

    async def compare_and_set_job_state(
        self,
        job_id: str,
        expected_states: Collection[str],
        state: str,
        values: Mapping[str, object] | None = None,
    ) -> bool: ...

    async def add_person_input(self, person_input: JobPersonInput) -> None: ...

    async def list_person_inputs(self, job_id: str) -> list[JobPersonInput]: ...

    async def add_item(self, item: JobItem) -> None: ...

    async def get_item(self, item_id: str) -> JobItem | None: ...

    async def list_items(self, job_id: str) -> list[JobItem]: ...

    async def update_item(self, item: JobItem) -> None: ...

    async def compare_and_set_item_state(
        self,
        item_id: str,
        expected_states: Collection[str],
        state: str,
        values: Mapping[str, object] | None = None,
    ) -> bool: ...

    async def list_claimable_item_ids(
        self, *, now: datetime, states: Collection[str], limit: int = 1
    ) -> list[str]: ...

    async def list_external_reconciliation_candidates(
        self, *, limit: int = 20
    ) -> list[JobItem]: ...

    async def claim_item(
        self,
        item_id: str,
        *,
        claimant_token: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
    ) -> bool: ...

    async def release_claim(self, item_id: str) -> bool: ...

    async def list_claimed_item_ids(self, *, claimant_token: str) -> Sequence[str]: ...


class GeneratedOutputRepository(Protocol):
    async def add_output(self, output: GeneratedOutputRecord) -> None: ...

    async def get_output(self, output_id: str) -> GeneratedOutputRecord | None: ...

    async def list_outputs(self, job_item_id: str) -> list[GeneratedOutputRecord]: ...


class JobExecutionEventRepository(Protocol):
    async def add_event(self, event: JobExecutionEvent) -> None: ...

    async def list_events(self, job_id: str) -> list[JobExecutionEvent]: ...


class JobUnitOfWork(UnitOfWork, Protocol):
    """Job repositories sharing the service-wide transaction boundary."""

    @property
    def jobs(self) -> JobRepository: ...

    @property
    def job_outputs(self) -> GeneratedOutputRepository: ...

    @property
    def job_events(self) -> JobExecutionEventRepository: ...
