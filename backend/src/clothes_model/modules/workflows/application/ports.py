"""Persistence ports for immutable Workflow versions."""

from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.workflows.domain import WorkflowValidationRun, WorkflowVersion


class WorkflowRepository(Protocol):
    async def add(self, workflow: WorkflowVersion) -> None: ...

    async def get(self, workflow_version_id: str) -> WorkflowVersion | None: ...

    async def list_versions(self, workflow_id: str) -> list[WorkflowVersion]: ...

    async def get_active(self, mode: str) -> WorkflowVersion | None: ...

    async def update_lifecycle(self, workflow: WorkflowVersion) -> None: ...

    async def add_validation(self, run: WorkflowValidationRun) -> None: ...


class WorkflowUnitOfWork(UnitOfWork, Protocol):
    @property
    def workflows(self) -> WorkflowRepository: ...

