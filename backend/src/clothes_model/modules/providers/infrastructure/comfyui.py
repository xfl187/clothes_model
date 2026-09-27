"""Production ComfyUI Provider adapter over the pinned server protocol.

The adapter resolves the current singleton physical node on every call and compares
it with the job's locked immutable Workflow.  It never mutates the stored Workflow
artifact, and it treats every upstream field as untrusted input.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import NoReturn, cast
from uuid import uuid4

import httpx2
from PIL import Image, UnidentifiedImageError

from clothes_model.infrastructure.security import AesGcmSecretCipher, SecretCryptoError
from clothes_model.infrastructure.storage import StorageError, WorkflowArtifactStorage
from clothes_model.modules.comfy.application import SECRET_PURPOSE, metadata_checks
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderError,
    ProviderInvocation,
    ProviderOutput,
    ProviderRequest,
    ProviderStatusResult,
    ProviderSubmission,
)
from clothes_model.modules.workflows.application.ports import WorkflowUnitOfWork
from clothes_model.modules.workflows.domain import ParsedManifest, parse_manifest

COMFY_ADAPTER_TYPE = "comfyui"
MAX_JSON_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 20_971_520
TEMP_CLEANUP_PATH = "/api/clothes-model/temp"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_segment(value: str) -> str:
    cleaned = _SAFE_NAME.sub("-", value).strip("-.")
    return cleaned[:120] or "item"


@dataclass(frozen=True, slots=True)
class _Access:
    endpoint: str
    headers: dict[str, str]
    timeout: int


@dataclass(slots=True)
class _Attempt:
    uploaded: list[str]
    prompt_id: str


class ComfyUIAdapter:
    adapter_type = COMFY_ADAPTER_TYPE

    def __init__(
        self,
        uow_factory: Callable[[], WorkflowUnitOfWork],
        artifacts: WorkflowArtifactStorage,
        cipher: AesGcmSecretCipher | None,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._artifacts = artifacts
        self._cipher = cipher
        self._client = client or httpx2.AsyncClient(trust_env=False, follow_redirects=False)
        self._owns_client = client is None
        self._attempts: dict[str, _Attempt] = {}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def availability(self, invocation: ProviderInvocation) -> str:
        try:
            access = await self._access(invocation)
        except ProviderError as error:
            if error.error_class == "temporarily_offline":
                return "temporarily_offline"
            return "unavailable_configuration"
        try:
            await self._request_json(access, "GET", "/system_stats")
        except ProviderError:
            return "temporarily_offline"
        return "available"

    async def capabilities(self, invocation: ProviderInvocation) -> ProviderCapabilities:
        _, _, manifest = await self._locked(invocation)
        return ProviderCapabilities.from_payload(manifest.capabilities)

    async def validate(self, invocation: ProviderInvocation) -> None:
        access, workflow, manifest = await self._locked(invocation)
        objects = await self._request_json(access, "GET", "/object_info")
        if _workflow_incompatible(workflow, manifest, objects):
            raise ProviderError(
                "temporarily_offline",
                "comfy_workflow_incompatible",
                "锁定的 Workflow 与当前节点不兼容。",
            )

    async def submit(
        self, invocation: ProviderInvocation, request: ProviderRequest
    ) -> ProviderSubmission:
        access, workflow, manifest = await self._locked(invocation)
        objects = await self._request_json(access, "GET", "/object_info")
        if _workflow_incompatible(workflow, manifest, objects):
            raise ProviderError(
                "temporarily_offline",
                "comfy_workflow_incompatible",
                "锁定的 Workflow 与当前节点不兼容。",
            )

        labels = ["person", "garment"]
        images = [request.person_bytes, request.garment_bytes]
        if "mask" in manifest.bindings:
            if request.mask_bytes is None:
                raise ProviderError(
                    "rejected_input", "comfy_mask_required", "Workflow 需要遮罩输入。"
                )
            labels.append("mask")
            images.append(request.mask_bytes)

        prefix = _safe_segment(request.job_item_id)
        uploaded: dict[str, str] = {}
        try:
            for label, content in zip(labels, images, strict=True):
                name = f"{prefix}-{label}-{uuid4().hex}.png"
                uploaded[label] = await self._upload(access, name, content)
        except ProviderError:
            await self._cleanup(access, list(uploaded.values()), None)
            raise

        prompt = copy.deepcopy(workflow)
        for label in labels:
            binding = manifest.bindings[label]
            _node_inputs(prompt, binding.node_id)[binding.input_name] = uploaded[label]
        seed_binding = manifest.bindings["seed"]
        _node_inputs(prompt, seed_binding.node_id)[seed_binding.input_name] = (
            request.seed if request.seed is not None else 0
        )
        candidate_binding = manifest.bindings["candidate_index"]
        _node_inputs(prompt, candidate_binding.node_id)[candidate_binding.input_name] = (
            request.candidate_index
        )

        client_id = f"clothes-model-{prefix}"
        body = {"prompt": prompt, "client_id": client_id}
        try:
            response = await self._client.post(
                f"{access.endpoint}/prompt",
                headers=access.headers,
                json=body,
                timeout=access.timeout,
            )
        except httpx2.ConnectError as error:
            await self._cleanup(access, list(uploaded.values()), None)
            raise ProviderError(
                "temporarily_offline", "comfy_connection_failed", "无法连接 ComfyUI 节点。"
            ) from error
        except (httpx2.TimeoutException, httpx2.TransportError) as error:
            # Transmission may have succeeded; never let this be retried automatically.
            raise ProviderError(
                "externally_ambiguous",
                "comfy_submit_outcome_unknown",
                "提交结果无法确认，可能需要人工核对。",
            ) from error
        if 300 <= response.status_code < 400:
            raise ProviderError(
                "invalid_configuration", "comfy_redirect_rejected", "节点返回了禁止的重定向。"
            )
        if response.status_code in {401, 403}:
            await self._cleanup(access, list(uploaded.values()), None)
            raise ProviderError(
                "invalid_configuration", "comfy_auth_failed", "ComfyUI 节点认证失败。"
            )
        if response.status_code in {400, 413, 422}:
            await self._cleanup(access, list(uploaded.values()), None)
            raise ProviderError(
                "rejected_input", "comfy_prompt_rejected", "ComfyUI 节点拒绝了本次提交。"
            )
        if response.status_code == 429 or response.status_code >= 500:
            return _raise_transient(response)
        if response.status_code != 200:
            await self._cleanup(access, list(uploaded.values()), None)
            raise ProviderError(
                "terminal_failure", "comfy_submit_failed", "ComfyUI 提交失败。"
            )
        payload = _json_body(response)
        prompt_id = payload.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id or len(prompt_id) > 200:
            await self._cleanup(access, list(uploaded.values()), None)
            raise ProviderError(
                "terminal_failure", "comfy_prompt_id_invalid", "ComfyUI 未返回有效执行标识。"
            )
        self._attempts[prompt_id] = _Attempt(uploaded=list(uploaded.values()), prompt_id=prompt_id)
        return ProviderSubmission(state="accepted", external_execution_id=prompt_id)

    async def query(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> ProviderStatusResult:
        access = await self._access(invocation)
        history = await self._request_json(access, "GET", f"/history/{external_execution_id}")
        record = history.get(external_execution_id)
        if isinstance(record, dict):
            status = cast(dict[str, object], record).get("status")
            status_map = cast(dict[str, object], status) if isinstance(status, dict) else {}
            state = status_map.get("status_str")
            completed = status_map.get("completed")
            if state in {"error", "failed"}:
                await self._finish(external_execution_id, access)
                return ProviderStatusResult(
                    state="failed",
                    error=ProviderError(
                        "terminal_failure", "comfy_execution_failed", "ComfyUI 执行失败。"
                    ),
                )
            if completed is True or state in {"success", "completed"}:
                return ProviderStatusResult(state="succeeded")
            return ProviderStatusResult(state="running")

        queue = await self._request_json(access, "GET", "/queue")
        if _queue_contains(queue, external_execution_id):
            return ProviderStatusResult(state="running")
        raise ProviderError(
            "externally_ambiguous",
            "comfy_execution_unknown",
            "ComfyUI 执行状态无法确认。",
        )

    async def cancel(self, invocation: ProviderInvocation, external_execution_id: str) -> bool:
        access = await self._access(invocation)
        queue = await self._request_json(access, "GET", "/queue")
        if not _queue_pending_contains(queue, external_execution_id):
            # Already running or unknown; interruption cannot be proven, so do not claim it.
            return False
        try:
            response = await self._client.post(
                f"{access.endpoint}/queue",
                headers=access.headers,
                json={"delete": [external_execution_id]},
                timeout=access.timeout,
            )
        except httpx2.HTTPError:
            return False
        if response.status_code not in {200, 204}:
            return False
        await self._finish(external_execution_id, access)
        return True

    async def fetch_outputs(
        self, invocation: ProviderInvocation, external_execution_id: str
    ) -> list[ProviderOutput]:
        access, _, manifest = await self._locked(invocation)
        history = await self._request_json(access, "GET", f"/history/{external_execution_id}")
        record = history.get(external_execution_id)
        record_map = cast(dict[str, object], record) if isinstance(record, dict) else {}
        outputs_value = record_map.get("outputs")
        outputs = cast(dict[str, object], outputs_value) if isinstance(outputs_value, dict) else {}
        collected: list[ProviderOutput] = []
        remote_outputs: list[str] = []
        for binding in manifest.outputs:
            node = outputs.get(binding.node_id)
            node_map = cast(dict[str, object], node) if isinstance(node, dict) else {}
            images = node_map.get("images")
            if not isinstance(images, list):
                raise ProviderError(
                    "terminal_failure", "comfy_output_missing", "声明的输出节点未返回图像。"
                )
            image_list = cast(list[object], images)
            if binding.output_index >= len(image_list) or not isinstance(
                image_list[binding.output_index], dict
            ):
                raise ProviderError(
                    "terminal_failure", "comfy_output_missing", "声明的输出索引不存在。"
                )
            ref = _output_ref(cast(dict[str, object], image_list[binding.output_index]))
            content = await self._fetch_image(access, ref)
            remote_outputs.append(ref["filename"])
            collected.append(
                ProviderOutput(
                    content=content,
                    content_type="image/png" if content.startswith(b"\x89PNG") else "image/jpeg",
                    seed=None,
                    actual_parameters={"bindings_schema_version": manifest.schema_version},
                )
            )
        await self._finish(external_execution_id, access, extra=remote_outputs)
        return collected

    async def _locked(
        self, invocation: ProviderInvocation
    ) -> tuple[_Access, dict[str, object], ParsedManifest]:
        workflow_id = invocation.vendor_parameters.get("workflow_version_id")
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ProviderError(
                "invalid_configuration", "comfy_workflow_unbound", "未锁定 ComfyUI Workflow。"
            )
        async with self._uow_factory() as uow:
            entity = await uow.workflows.get(workflow_id)
        if entity is None:
            raise ProviderError(
                "invalid_configuration", "comfy_workflow_missing", "锁定的 Workflow 不存在。"
            )
        try:
            workflow_bytes = self._artifacts.read(entity.workflow_path)
            manifest_bytes = self._artifacts.read(entity.manifest_path)
        except StorageError as error:
            raise ProviderError(
                "invalid_configuration", "comfy_workflow_unavailable", "Workflow 制品不可用。"
            ) from error
        if (
            hashlib.sha256(workflow_bytes).hexdigest() != entity.workflow_sha256
            or hashlib.sha256(manifest_bytes).hexdigest() != entity.manifest_sha256
        ):
            raise ProviderError(
                "invalid_configuration", "comfy_workflow_corrupt", "Workflow 制品校验失败。"
            )
        try:
            workflow = cast(dict[str, object], json.loads(workflow_bytes))
            manifest = parse_manifest(cast(dict[str, object], json.loads(manifest_bytes)), workflow)
        except ValueError as error:
            raise ProviderError(
                "invalid_configuration", "comfy_workflow_invalid", "Workflow 结构无效。"
            ) from error
        access = await self._access(invocation)
        return access, workflow, manifest

    async def _access(self, invocation: ProviderInvocation) -> _Access:
        async with self._uow_factory() as uow:
            node = await uow.comfy_node.get()
        if node is None or not node.enabled:
            raise ProviderError(
                "temporarily_offline", "comfy_node_unavailable", "ComfyUI 节点未配置或未启用。"
            )
        credential: str | None = None
        if node.credential_envelope:
            if self._cipher is None:
                raise ProviderError(
                    "invalid_configuration", "comfy_secret_unavailable", "节点凭据不可用。"
                )
            try:
                credential = self._cipher.decrypt(
                    node.credential_envelope, purpose=SECRET_PURPOSE, record_id="default"
                )
            except SecretCryptoError as error:
                raise ProviderError(
                    "invalid_configuration", "comfy_secret_invalid", "节点凭据无法解密。"
                ) from error
        headers = {"Accept": "application/json"}
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        return _Access(node.endpoint, headers, node.timeout_seconds)

    async def _request_json(
        self,
        access: _Access,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
    ) -> dict[str, object]:
        try:
            response = await self._client.request(
                method,
                f"{access.endpoint}{path}",
                headers=access.headers,
                json=json_body,
                timeout=access.timeout,
            )
        except httpx2.HTTPError as error:
            raise ProviderError(
                "temporarily_offline", "comfy_connection_failed", "无法连接 ComfyUI 节点。"
            ) from error
        if 300 <= response.status_code < 400:
            raise ProviderError(
                "invalid_configuration", "comfy_redirect_rejected", "节点返回了禁止的重定向。"
            )
        if response.status_code in {401, 403}:
            raise ProviderError(
                "invalid_configuration", "comfy_auth_failed", "ComfyUI 节点认证失败。"
            )
        if response.status_code == 429 or response.status_code >= 500:
            return _raise_transient(response)
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderError("terminal_failure", "comfy_request_failed", "ComfyUI 请求失败。")
        return _json_body(response)

    async def _upload(self, access: _Access, name: str, content: bytes) -> str:
        try:
            response = await self._client.post(
                f"{access.endpoint}/upload/image",
                headers=access.headers,
                files={"image": (name, content, "image/png")},
                data={"type": "temp", "overwrite": "false"},
                timeout=access.timeout,
            )
        except httpx2.HTTPError as error:
            raise ProviderError(
                "temporarily_offline", "comfy_connection_failed", "无法连接 ComfyUI 节点。"
            ) from error
        if 300 <= response.status_code < 400:
            raise ProviderError(
                "invalid_configuration", "comfy_redirect_rejected", "节点返回了禁止的重定向。"
            )
        if response.status_code in {401, 403}:
            raise ProviderError(
                "invalid_configuration", "comfy_auth_failed", "ComfyUI 节点认证失败。"
            )
        if response.status_code in {400, 413, 422}:
            raise ProviderError("rejected_input", "comfy_upload_rejected", "节点拒绝了输入素材。")
        if response.status_code == 429 or response.status_code >= 500:
            return _raise_transient(response)
        if response.status_code != 200:
            raise ProviderError("terminal_failure", "comfy_upload_failed", "输入素材上传失败。")
        payload = _json_body(response)
        remote = payload.get("name")
        if isinstance(remote, str):
            remote = remote.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if (
            not isinstance(remote, str)
            or not remote
            or len(remote) > 255
            or remote in {".", ".."}
        ):
            raise ProviderError(
                "terminal_failure", "comfy_upload_invalid", "节点返回了不安全的文件引用。"
            )
        return remote

    async def _fetch_image(self, access: _Access, ref: dict[str, str]) -> bytes:
        try:
            response = await self._client.get(
                f"{access.endpoint}/view",
                headers=access.headers,
                params=ref,
                timeout=access.timeout,
            )
        except httpx2.HTTPError as error:
            raise ProviderError(
                "temporarily_offline", "comfy_connection_failed", "输出下载失败。"
            ) from error
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if response.status_code != 200 or content_type not in {"image/png", "image/jpeg"}:
            raise ProviderError("terminal_failure", "comfy_output_invalid", "输出响应无效。")
        if not response.content or len(response.content) > MAX_OUTPUT_BYTES:
            raise ProviderError("terminal_failure", "comfy_output_invalid", "输出大小无效。")
        try:
            with Image.open(io.BytesIO(response.content)) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as error:
            raise ProviderError(
                "terminal_failure", "comfy_output_invalid", "输出不是有效图像。"
            ) from error
        return response.content

    async def _finish(
        self, external_execution_id: str, access: _Access, *, extra: list[str] | None = None
    ) -> None:
        attempt = self._attempts.pop(external_execution_id, None)
        if attempt is None:
            return
        files = list(attempt.uploaded)
        if extra:
            files.extend(str(item) for item in extra)
        await self._cleanup(access, files, external_execution_id)

    async def _cleanup(
        self, access: _Access, files: list[str], prompt_id: str | None
    ) -> None:
        if not files and prompt_id is None:
            return
        with suppress(Exception):
            await self._client.request(
                "DELETE",
                f"{access.endpoint}{TEMP_CLEANUP_PATH}",
                headers=access.headers,
                json={"files": files, "prompt_id": prompt_id},
                timeout=access.timeout,
            )


def _raise_transient(_response: httpx2.Response) -> NoReturn:
    raise ProviderError(
        "retryable_transient",
        "comfy_temporarily_unavailable",
        "ComfyUI 节点暂时不可用。",
        retryable=True,
    )


def _json_body(response: httpx2.Response) -> dict[str, object]:
    if len(response.content) > MAX_JSON_BYTES:
        raise ProviderError(
            "terminal_failure", "comfy_response_too_large", "节点响应超过安全上限。"
        )
    try:
        value: object = response.json()
    except (TypeError, ValueError) as error:
        raise ProviderError(
            "terminal_failure", "comfy_response_invalid", "节点返回了无效 JSON。"
        ) from error
    if not isinstance(value, dict):
        raise ProviderError("terminal_failure", "comfy_response_invalid", "节点响应结构无效。")
    return cast(dict[str, object], value)


def _workflow_incompatible(
    workflow: dict[str, object], manifest: ParsedManifest, objects: dict[str, object]
) -> bool:
    return any(
        item.status == "failed" for item in metadata_checks(workflow, manifest, objects)
    )


def _queue_contains(queue: dict[str, object], prompt_id: str) -> bool:
    for key in ("queue_pending", "queue_running"):
        entries = queue.get(key)
        if not isinstance(entries, list):
            continue
        for entry in cast(list[object], entries):
            if _entry_matches(entry, prompt_id):
                return True
    return False


def _queue_pending_contains(queue: dict[str, object], prompt_id: str) -> bool:
    entries = queue.get("queue_pending")
    if not isinstance(entries, list):
        return False
    return any(_entry_matches(entry, prompt_id) for entry in cast(list[object], entries))


def _entry_matches(entry: object, prompt_id: str) -> bool:
    if not isinstance(entry, list):
        return False
    row = cast(list[object], entry)
    return len(row) > 1 and row[1] == prompt_id


def _output_ref(raw: dict[str, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("filename", "subfolder", "type"):
        value = raw.get(key, "")
        if not isinstance(value, str) or len(value) > 500:
            raise ProviderError(
                "terminal_failure", "comfy_output_invalid", "输出文件引用格式无效。"
            )
        result[key] = value
    if (
        not result["filename"]
        or result["type"] not in {"output", "temp"}
        or ".." in result["filename"]
        or ".." in result["subfolder"]
        or "/" in result["filename"]
        or "\\" in result["filename"]
    ):
        raise ProviderError("terminal_failure", "comfy_output_invalid", "输出文件引用不安全。")
    return result


def _node_inputs(prompt: dict[str, object], node_id: str) -> dict[str, object]:
    node = prompt.get(node_id)
    if not isinstance(node, dict):
        raise ProviderError(
            "invalid_configuration", "comfy_workflow_invalid", "Workflow 节点缺失。"
        )
    inputs = cast(dict[str, object], node).get("inputs")
    if not isinstance(inputs, dict):
        raise ProviderError(
            "invalid_configuration", "comfy_workflow_invalid", "Workflow 输入缺失。"
        )
    return cast(dict[str, object], inputs)


__all__ = ["COMFY_ADAPTER_TYPE", "ComfyUIAdapter"]
