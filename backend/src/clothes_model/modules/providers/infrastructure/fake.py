"""Deterministic in-process provider used by Phase 3 tests and development."""

import io
from dataclasses import dataclass

from PIL import Image

from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderError,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
    ProviderStatusResult,
    ProviderSubmission,
)

FAKE_ADAPTER_TYPE = "fake_image_edit"


@dataclass
class _Execution:
    scenario: str
    polls: int = 0
    request: ProviderRequest | None = None


def _int_param(parameters: dict[str, object], key: str, default: int) -> int:
    value = parameters.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _png(seed: int, candidate_index: int) -> bytes:
    color = ((seed + candidate_index * 37) % 256, (seed // 3) % 256, (seed // 7) % 256)
    image = Image.new("RGB", (32, 32), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class FakeImageEditAdapter:
    """Deterministic adapter with controllable success/offline/transient/ambiguous outcomes.

    The scenario is selected through the provider configuration's ``scenario`` vendor
    parameter so the same code path is exercised without any network access.
    """

    adapter_type = FAKE_ADAPTER_TYPE

    def __init__(self) -> None:
        self._executions: dict[str, _Execution] = {}

    def _scenario(self, invocation: ProviderInvocation) -> str:
        return str(invocation.vendor_parameters.get("scenario", "success"))

    async def availability(self, invocation: ProviderInvocation) -> str:
        scenario = self._scenario(invocation)
        if scenario == "offline":
            return "temporarily_offline"
        if scenario == "invalid_config":
            return "unavailable_configuration"
        if scenario == "disabled":
            return "disabled"
        return "available"

    async def capabilities(self, invocation: ProviderInvocation) -> ProviderCapabilities:
        scenario = self._scenario(invocation)
        return ProviderCapabilities(
            manual_mask=True,
            multiple_candidates=True,
            interrupt_running=scenario != "uncancellable",
            region_mask=True,
            max_candidates=_int_param(invocation.vendor_parameters, "max_candidates", 4),
            source="adapter",
            verification="verified" if scenario != "invalid_config" else "unavailable",
        )

    async def validate(self, invocation: ProviderInvocation) -> None:
        availability = await self.availability(invocation)
        if availability != "available":
            raise ProviderError(
                "invalid_configuration",
                "provider_validation_failed",
                "Provider 配置验证失败。",
            )

    async def submit(
        self, invocation: ProviderInvocation, request: ProviderRequest
    ) -> ProviderSubmission:
        scenario = self._scenario(invocation)
        if scenario == "offline":
            raise ProviderError("temporarily_offline", "provider_offline", "Provider 暂时离线。")
        if scenario == "invalid_config":
            raise ProviderError(
                "invalid_configuration", "provider_configuration_invalid", "Provider 配置无效。"
            )
        if scenario == "reject":
            raise ProviderError(
                "rejected_input", "provider_input_rejected", "Provider 拒绝了输入。"
            )
        external_id = f"fake-{request.job_item_id}"
        execution = self._executions.get(external_id)
        if execution is None:
            self._executions[external_id] = _Execution(scenario=scenario, request=request)
        else:
            # A retry resubmits but keeps accumulated polling history so transient
            # failures eventually resolve without external state.
            execution.request = request
        return ProviderSubmission(state="accepted", external_execution_id=external_id)

    async def query(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> ProviderStatusResult:
        execution = self._executions.get(external_execution_id)
        if execution is None:
            raise ProviderError(
                "externally_ambiguous",
                "provider_execution_unknown",
                "Provider 执行状态无法确认。",
            )
        execution.polls += 1
        if execution.scenario == "ambiguous":
            raise ProviderError(
                "externally_ambiguous",
                "provider_execution_unknown",
                "Provider 执行状态无法确认。",
            )
        if execution.scenario == "running":
            return ProviderStatusResult(state="running")
        if execution.scenario == "terminal":
            return ProviderStatusResult(
                state="failed",
                error=ProviderError("terminal_failure", "provider_execution_failed", "执行失败。"),
            )
        if execution.scenario == "transient":
            failures = _int_param(invocation.vendor_parameters, "transient_failures", 1)
            if execution.polls <= failures:
                return ProviderStatusResult(
                    state="failed",
                    error=ProviderError(
                        "retryable_transient",
                        "provider_transient",
                        "临时故障。",
                        retryable=True,
                    ),
                )
            return ProviderStatusResult(state="succeeded")
        running_polls = _int_param(invocation.vendor_parameters, "running_polls", 0)
        if execution.polls <= running_polls:
            return ProviderStatusResult(state="running")
        return ProviderStatusResult(state="succeeded")

    async def cancel(self, invocation: ProviderInvocation, external_execution_id: str) -> bool:
        execution = self._executions.get(external_execution_id)
        if execution is None:
            return False
        return self._scenario(invocation) != "uncancellable"

    async def fetch_outputs(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> list[ProviderOutput]:
        execution = self._executions.get(external_execution_id)
        if execution is None or execution.request is None:
            raise ProviderError(
                "externally_ambiguous",
                "provider_output_missing",
                "无法获取 Provider 输出。",
            )
        request = execution.request
        seed = request.seed if request.seed is not None else 0
        return [
            ProviderOutput(
                content=_png(seed, request.candidate_index),
                content_type="image/png",
                seed=seed,
                actual_parameters={"scenario": execution.scenario, "steps": 20},
            )
        ]
