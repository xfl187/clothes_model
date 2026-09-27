"""Volcengine Ark Seedream synchronous image-generation adapter."""

from __future__ import annotations

import base64
import binascii
from typing import Any, cast
from urllib.parse import urlsplit

import httpx2

from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderError,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
    ProviderStatusResult,
    ProviderSubmission,
)

ARK_ADAPTER_TYPE = "volcengine_ark_seedream"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "doubao-seedream-4-5-251128"
PROMPT_TEMPLATE_VERSION = "virtual-try-on-v1"
MAX_OUTPUT_BYTES = 20_971_520

_PROMPT = (
    "Use the first reference image as the person and the second as the target garment. "
    "Create a realistic virtual try-on image that replaces only the target garment. "
    "Preserve the person's identity, face, pose, body proportions, background, framing, "
    "lighting, and all non-target clothing. Return one complete image."
)


def _validate_boundary(invocation: ProviderInvocation) -> None:
    endpoint = invocation.endpoint.rstrip("/")
    parsed = urlsplit(endpoint)
    if (
        endpoint != ARK_BASE_URL
        or parsed.scheme != "https"
        or parsed.hostname != "ark.cn-beijing.volces.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise ProviderError(
            "invalid_configuration",
            "ark_endpoint_invalid",
            "Seedream 仅允许使用火山方舟北京官方 API 地址。",
        )
    if invocation.model != ARK_MODEL:
        raise ProviderError(
            "invalid_configuration",
            "ark_model_unsupported",
            "Seedream Provider 模型不受支持。",
        )
    if not 1 <= invocation.timeout_seconds <= 300:
        raise ProviderError(
            "invalid_configuration", "ark_timeout_invalid", "请求超时必须在 1 到 300 秒之间。"
        )


def _data_url(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        content_type = "image/jpeg"
    else:
        raise ProviderError(
            "rejected_input", "ark_image_type_unsupported", "仅支持 PNG 或 JPEG 输入图片。"
        )
    return f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"


def _error_code(response: httpx2.Response) -> str:
    try:
        payload = cast(dict[str, Any], response.json())
    except (ValueError, TypeError):
        return f"http_{response.status_code}"
    error = payload.get("error")
    if isinstance(error, dict):
        safe_error = cast(dict[str, object], error)
        code = safe_error.get("code")
        if isinstance(code, str) and code:
            return code[:80]
    code = payload.get("code")
    return code[:80] if isinstance(code, str) and code else f"http_{response.status_code}"


def _map_http_error(response: httpx2.Response) -> ProviderError:
    code = _error_code(response)
    status = response.status_code
    if status in {401, 403}:
        return ProviderError("invalid_configuration", code, "火山方舟凭据或权限无效。")
    if status in {400, 413, 422}:
        return ProviderError("rejected_input", code, "火山方舟拒绝了本次输入。")
    if status == 429 or status >= 500:
        return ProviderError(
            "retryable_transient", code, "火山方舟暂时不可用，请稍后重试。", retryable=True
        )
    return ProviderError("terminal_failure", code, "火山方舟请求失败。")


class VolcengineArkSeedreamAdapter:
    """One-image Seedream adapter with an injectable HTTP transport for deterministic tests."""

    adapter_type = ARK_ADAPTER_TYPE

    def __init__(self, client: httpx2.AsyncClient | None = None) -> None:
        self._client = client or httpx2.AsyncClient(trust_env=False, follow_redirects=False)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def availability(self, invocation: ProviderInvocation) -> str:
        try:
            _validate_boundary(invocation)
        except ProviderError:
            return "unavailable_configuration"
        return "available" if invocation.credential else "unavailable_configuration"

    async def capabilities(self, invocation: ProviderInvocation) -> ProviderCapabilities:
        _validate_boundary(invocation)
        return ProviderCapabilities(
            multiple_candidates=False,
            manual_mask=False,
            interrupt_running=False,
            max_candidates=1,
            source="adapter",
            verification="declared",
        )

    async def submit(
        self, invocation: ProviderInvocation, request: ProviderRequest
    ) -> ProviderSubmission:
        _validate_boundary(invocation)
        if not invocation.credential:
            raise ProviderError(
                "invalid_configuration", "ark_api_key_missing", "火山方舟 API Key 未配置。"
            )
        if request.candidate_count != 1 or request.candidate_index != 0:
            raise ProviderError(
                "rejected_input", "ark_single_candidate_only", "Seedream 当前仅支持单候选结果。"
            )
        payload = {
            "model": ARK_MODEL,
            "prompt": _PROMPT,
            "image": [_data_url(request.person_bytes), _data_url(request.garment_bytes)],
            "size": "2K",
            "response_format": "b64_json",
            "sequential_image_generation": "disabled",
            "stream": False,
            "watermark": True,
        }
        try:
            response = await self._client.post(
                f"{ARK_BASE_URL}/images/generations",
                headers={"Authorization": f"Bearer {invocation.credential}"},
                json=payload,
                timeout=invocation.timeout_seconds,
            )
        except (httpx2.TimeoutException, httpx2.TransportError) as exc:
            raise ProviderError(
                "externally_ambiguous",
                "ark_request_outcome_unknown",
                "请求可能已被火山方舟接收，结果无法确认。",
            ) from exc
        if response.status_code != 200:
            raise _map_http_error(response)
        try:
            decoded = cast(dict[str, Any], response.json())
            data_value = decoded["data"]
            data = cast(list[object], data_value) if isinstance(data_value, list) else []
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("invalid data")
            output_data = cast(dict[str, object], data[0])
            encoded = output_data["b64_json"]
            if not isinstance(encoded, str):
                raise ValueError("missing b64_json")
            content = base64.b64decode(encoded, validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise ProviderError(
                "terminal_failure", "ark_response_invalid", "火山方舟返回了无效图片结果。"
            ) from exc
        if not content or len(content) > MAX_OUTPUT_BYTES:
            raise ProviderError(
                "terminal_failure", "ark_output_size_invalid", "火山方舟输出大小无效。"
            )
        content_type = "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
        if content_type == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
            raise ProviderError(
                "terminal_failure", "ark_output_type_invalid", "火山方舟输出格式无效。"
            )
        output = ProviderOutput(
            content=content,
            content_type=content_type,
            seed=request.seed,
            actual_parameters={
                "model": ARK_MODEL,
                "size": "2K",
                "response_format": "b64_json",
                "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            },
        )
        return ProviderSubmission(state="completed", outputs=(output,))

    async def query(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> ProviderStatusResult:
        raise ProviderError(
            "externally_ambiguous", "ark_query_unsupported", "同步 Seedream 请求不支持状态查询。"
        )

    async def cancel(self, invocation: ProviderInvocation, external_execution_id: str) -> bool:
        return False

    async def fetch_outputs(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> list[ProviderOutput]:
        raise ProviderError(
            "externally_ambiguous",
            "ark_fetch_unsupported",
            "同步 Seedream 输出只能从原始响应获取。",
        )


__all__ = [
    "ARK_ADAPTER_TYPE",
    "ARK_BASE_URL",
    "ARK_MODEL",
    "PROMPT_TEMPLATE_VERSION",
    "VolcengineArkSeedreamAdapter",
]
