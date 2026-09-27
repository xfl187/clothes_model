"""Job command services: cancellation, retry, requery, and finish-failed."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.modules.jobs.domain import (
    TERMINAL_JOB_ITEM_STATES,
    Job,
    JobItem,
)
from clothes_model.modules.jobs.infrastructure.execution import JobExecutionService
from clothes_model.modules.providers.application.ports import ProviderRegistryPort
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.domain import ProviderError

NON_TERMINAL_STATES = (
    "queued",
    "waiting_provider",
    "preparing",
    "running",
    "needs_attention",
)


class JobCommandError(RuntimeError):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


class JobCommandService:
    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        provider_service: ProviderConfigService,
        registry: ProviderRegistryPort,
        execution: JobExecutionService,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._provider_service = provider_service
        self._registry = registry
        self._execution = execution
        self._clock = clock or (lambda: datetime.now(UTC))

    async def _job_of_item(self, uow: SqlAlchemyUnitOfWork, item: JobItem) -> Job:
        job = await uow.jobs.get_job(item.job_id)
        if job is None:
            raise JobCommandError(404, "not_found", "任务不存在。")
        return job

    async def cancel_item(self, item_id: str) -> Job:
        async with self._uow_factory() as uow:
            item = await uow.jobs.get_item(item_id)
            if item is None:
                raise JobCommandError(404, "not_found", "候选任务不存在。")
            job = await self._job_of_item(uow, item)
        if item.state not in TERMINAL_JOB_ITEM_STATES:
            await self._best_effort_cancel(item, job)
            await self._cancel_items([item.id])
        await self._execution.recompute(job.id)
        return await self._reload(job.id)

    async def cancel_job(self, job_id: str) -> Job:
        async with self._uow_factory() as uow:
            job = await uow.jobs.get_job(job_id)
            if job is None:
                raise JobCommandError(404, "not_found", "任务不存在。")
            items = await uow.jobs.list_items(job_id)
        unfinished = [item for item in items if item.state not in TERMINAL_JOB_ITEM_STATES]
        for item in unfinished:
            await self._best_effort_cancel(item, job)
        await self._cancel_items([item.id for item in unfinished])
        await self._execution.recompute(job.id)
        return await self._reload(job.id)

    async def retry_item(
        self, item_id: str, *, reason: str | None = None, provider_id: str | None = None
    ) -> tuple[Job, str]:
        async with self._uow_factory() as uow:
            item = await uow.jobs.get_item(item_id)
            if item is None:
                raise JobCommandError(404, "not_found", "候选任务不存在。")
            job = await self._job_of_item(uow, item)
            if item.state not in {"failed", "needs_attention"}:
                raise JobCommandError(409, "job_state_conflict", "仅失败或待处理的候选可以重试。")
            siblings = await uow.jobs.list_items(item.job_id)
            attempt = max(
                (
                    entry.attempt
                    for entry in siblings
                    if entry.candidate_index == item.candidate_index
                ),
                default=item.attempt,
            ) + 1
            new_id = str(uuid4())
            now = self._clock()
            await uow.jobs.add_item(
                JobItem(
                    id=new_id,
                    job_id=item.job_id,
                    person_asset_id=item.person_asset_id,
                    candidate_index=item.candidate_index,
                    attempt=attempt,
                    state="queued",
                    retry_of_job_item_id=item.id,
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.jobs.compare_and_set_item_state(
                item.id,
                (*NON_TERMINAL_STATES, "failed"),
                item.state,
                {"superseded_by_job_item_id": new_id, "updated_at": now},
            )
            await uow.commit()
        if provider_id is not None:
            await self._validate_provider(provider_id)
        await self._execution.recompute(job.id)
        return await self._reload(job.id), new_id

    async def requery_item(self, item_id: str) -> Job:
        async with self._uow_factory() as uow:
            item = await uow.jobs.get_item(item_id)
            if item is None:
                raise JobCommandError(404, "not_found", "候选任务不存在。")
            job = await self._job_of_item(uow, item)
        if item.state != "needs_attention":
            raise JobCommandError(409, "job_state_conflict", "仅待处理候选可以重新查询。")
        if not item.external_execution_id:
            raise JobCommandError(409, "external_state_unknown", "外部执行标识缺失，无法重新查询。")
        invocation, _, _ = await self._provider_service.resolve_invocation(
            job.provider_id, job.provider_revision_id
        )
        adapter = self._registry.resolve(invocation.adapter_type)
        try:
            status = await adapter.query(invocation, item.external_execution_id)
        except ProviderError as error:
            if error.error_class == "externally_ambiguous":
                return await self._reload(job.id)
            await self._execution.finish_failed(item_id, error.code, error.detail)
            return await self._reload(job.id)
        if status.state == "succeeded":
            await self._execution.persist_success(
                item, job, invocation, item.external_execution_id, expected=("needs_attention",)
            )
        elif status.state == "running":
            async with self._uow_factory() as uow:
                await uow.jobs.compare_and_set_item_state(
                    item_id, ("needs_attention",), "running", {"updated_at": self._clock()}
                )
                await uow.commit()
            await self._execution.recompute(job.id)
        else:
            code = status.error.code if status.error is not None else "provider_failure"
            detail = status.error.detail if status.error is not None else "生成失败。"
            await self._execution.finish_failed(item_id, code, detail)
        return await self._reload(job.id)

    async def finish_failed(self, item_id: str, reason: str) -> Job:
        async with self._uow_factory() as uow:
            item = await uow.jobs.get_item(item_id)
            if item is None:
                raise JobCommandError(404, "not_found", "候选任务不存在。")
            job = await self._job_of_item(uow, item)
            if item.state != "needs_attention":
                raise JobCommandError(409, "job_state_conflict", "仅待处理候选可以结束为失败。")
        await self._execution.finish_failed(item_id, "operator_finished_failed", reason)
        return await self._reload(job.id)

    async def _best_effort_cancel(self, item: JobItem, job: Job) -> None:
        if item.state != "running" or not item.external_execution_id:
            return
        try:
            invocation, _, _ = await self._provider_service.resolve_invocation(
                job.provider_id, job.provider_revision_id
            )
            adapter = self._registry.resolve(invocation.adapter_type)
            await adapter.cancel(invocation, item.external_execution_id)
        except ProviderError:
            return

    async def _cancel_items(self, item_ids: list[str]) -> None:
        now = self._clock()
        async with self._uow_factory() as uow:
            for item_id in item_ids:
                await uow.jobs.compare_and_set_item_state(
                    item_id,
                    NON_TERMINAL_STATES,
                    "cancelled",
                    {
                        "claimant_token": None,
                        "claimed_at": None,
                        "lease_expires_at": None,
                        "next_attempt_at": None,
                        "updated_at": now,
                    },
                )
            await uow.commit()

    async def _validate_provider(self, provider_id: str) -> None:
        config = await self._provider_service.get(provider_id)
        if config is None or config.state not in {"active", "validated"}:
            raise JobCommandError(409, "provider_not_usable", "所选 Provider 不可用。")
        revision = await self._provider_service.current_revision(provider_id)
        if revision is not None and revision.adapter_type == "comfyui":
            async with self._uow_factory() as uow:
                active = await uow.workflows.get_active("precise_try_on")
            if active is None:
                raise JobCommandError(409, "workflow_not_active", "当前没有可用的换装 Workflow。")

    async def _reload(self, job_id: str) -> Job:
        async with self._uow_factory() as uow:
            job = await uow.jobs.get_job(job_id)
        if job is None:
            raise JobCommandError(404, "not_found", "任务不存在。")
        return job
