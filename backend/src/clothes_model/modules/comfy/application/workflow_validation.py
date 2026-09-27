"""Bounded live validation of immutable ComfyUI workflows."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import io
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

import httpx2
from PIL import Image, UnidentifiedImageError

from clothes_model.infrastructure.security import AesGcmSecretCipher, SecretCryptoError
from clothes_model.modules.comfy.application.ports import ComfyUnitOfWork
from clothes_model.modules.comfy.application.service import SECRET_PURPOSE
from clothes_model.modules.workflows.domain import ParsedManifest

MAX_JSON_BYTES = 2_000_000
MAX_IMAGE_BYTES = 25_000_000


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    key: str
    status: str
    detail: str

    def payload(self) -> dict[str, str]:
        return {"key": self.key, "status": self.status, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class LiveValidationResult:
    status: str
    checks: tuple[ValidationCheck, ...]
    node_fingerprint: str | None
    server_version: str | None


class ComfyValidationError(RuntimeError):
    def __init__(self, key: str, detail: str, *, status: str = "failed") -> None:
        super().__init__(detail)
        self.key = key
        self.detail = detail
        self.status = status


@dataclass(frozen=True, slots=True)
class _Access:
    endpoint: str
    headers: dict[str, str]
    timeout: int


class ComfyWorkflowValidator:
    """Validate node compatibility and execute one sanitized bounded prompt."""

    def __init__(
        self,
        uow_factory: Callable[[], ComfyUnitOfWork],
        cipher: AesGcmSecretCipher | None,
        client: httpx2.AsyncClient,
    ) -> None:
        self._uow_factory = uow_factory
        self._cipher = cipher
        self._client = client

    async def validate(
        self, workflow: dict[str, object], manifest: ParsedManifest
    ) -> LiveValidationResult:
        checks: list[ValidationCheck] = []
        try:
            access = await self._access()
            system = await self._json(access, "GET", "/system_stats")
            objects = await self._json(access, "GET", "/object_info")
            version = self._server_version(system)
            fingerprint = hashlib.sha256(
                json.dumps(objects, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            checks.extend(self._check_metadata(workflow, manifest, objects))
            if any(item.status == "failed" for item in checks):
                return LiveValidationResult("incompatible", tuple(checks), fingerprint, version)
            checks.append(
                ValidationCheck("node_metadata", "passed", "节点元数据满足 Workflow 要求。")
            )
            execution_checks = await self._minimal_run(access, workflow, manifest)
            checks.extend(execution_checks)
            status = "passed" if all(item.status == "passed" for item in checks) else "failed"
            return LiveValidationResult(status, tuple(checks), fingerprint, version)
        except ComfyValidationError as error:
            checks.append(ValidationCheck(error.key, "failed", error.detail))
            return LiveValidationResult(error.status, tuple(checks), None, None)

    async def _access(self) -> _Access:
        async with self._uow_factory() as uow:
            config = await uow.comfy_node.get()
        if config is None or not config.enabled:
            raise ComfyValidationError(
                "node_available", "ComfyUI 节点未配置或未启用。", status="offline"
            )
        credential: str | None = None
        if config.credential_envelope:
            if self._cipher is None:
                raise ComfyValidationError("node_auth", "节点凭据存储当前不可用。")
            try:
                credential = self._cipher.decrypt(
                    config.credential_envelope, purpose=SECRET_PURPOSE, record_id="default"
                )
            except SecretCryptoError as error:
                raise ComfyValidationError("node_auth", "节点凭据无法解密。") from error
        headers = {"Accept": "application/json"}
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        return _Access(config.endpoint, headers, config.timeout_seconds)

    async def _json(
        self,
        access: _Access,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        try:
            response = await self._client.request(
                method,
                f"{access.endpoint}{path}",
                headers=access.headers,
                json=json_body,
                params=params,
                timeout=access.timeout,
            )
        except Exception as error:
            raise ComfyValidationError(
                "node_available", "无法连接 ComfyUI 节点。", status="offline"
            ) from error
        if 300 <= response.status_code < 400:
            raise ComfyValidationError("node_response", "节点返回了禁止的重定向。")
        if response.status_code < 200 or response.status_code >= 300:
            raise ComfyValidationError("node_response", "节点拒绝了校验请求。")
        if len(response.content) > MAX_JSON_BYTES:
            raise ComfyValidationError("node_response", "节点 JSON 响应超过安全上限。")
        try:
            value: object = response.json()
        except (TypeError, ValueError) as error:
            raise ComfyValidationError("node_response", "节点返回了无效 JSON。") from error
        if not isinstance(value, dict):
            raise ComfyValidationError("node_response", "节点 JSON 响应结构无效。")
        return cast(dict[str, object], value)

    async def _upload(self, access: _Access, label: str, content: bytes) -> str:
        try:
            response = await self._client.post(
                f"{access.endpoint}/upload/image",
                headers=access.headers,
                files={"image": (f"validation-{uuid4().hex}-{label}.png", content, "image/png")},
                data={"type": "temp", "overwrite": "false"},
                timeout=access.timeout,
            )
        except Exception as error:
            raise ComfyValidationError("fixture_upload", "校验图片上传失败。") from error
        if response.status_code < 200 or response.status_code >= 300:
            raise ComfyValidationError("fixture_upload", "节点拒绝了校验图片。")
        if len(response.content) > MAX_JSON_BYTES:
            raise ComfyValidationError("fixture_upload", "上传响应超过安全上限。")
        try:
            body: object = response.json()
        except (TypeError, ValueError) as error:
            raise ComfyValidationError("fixture_upload", "上传响应格式无效。") from error
        body_map = cast(dict[str, object], body) if isinstance(body, dict) else {}
        if not isinstance(body_map.get("name"), str):
            raise ComfyValidationError("fixture_upload", "上传响应缺少安全文件引用。")
        name = cast(str, body_map["name"])
        if not name or len(name) > 255 or "/" in name or "\\" in name or name in {".", ".."}:
            raise ComfyValidationError("fixture_upload", "上传响应包含不安全文件引用。")
        return name

    async def _minimal_run(
        self, access: _Access, workflow: dict[str, object], manifest: ParsedManifest
    ) -> list[ValidationCheck]:
        fixture = self._fixture_png()
        uploaded: list[str] = []
        prompt_id: str | None = None
        checks: list[ValidationCheck] = []
        try:
            for label in ("person", "garment") + (("mask",) if "mask" in manifest.bindings else ()):
                uploaded.append(await self._upload(access, label, fixture))
            prompt = copy.deepcopy(workflow)
            image_labels = ["person", "garment"] + (["mask"] if "mask" in manifest.bindings else [])
            for label, remote_name in zip(image_labels, uploaded, strict=True):
                binding = manifest.bindings[label]
                cast(dict[str, object], cast(dict[str, object], prompt[binding.node_id])["inputs"])[
                    binding.input_name
                ] = remote_name
            for label, value in (("seed", 1), ("candidate_index", 0)):
                binding = manifest.bindings[label]
                cast(dict[str, object], cast(dict[str, object], prompt[binding.node_id])["inputs"])[
                    binding.input_name
                ] = value
            submitted = await self._json(
                access,
                "POST",
                "/prompt",
                json_body={"prompt": prompt, "client_id": f"validation-{uuid4().hex}"},
            )
            raw_prompt_id = submitted.get("prompt_id")
            if not isinstance(raw_prompt_id, str) or not raw_prompt_id or len(raw_prompt_id) > 200:
                raise ComfyValidationError("test_submit", "节点未返回有效执行标识。")
            prompt_id = raw_prompt_id
            history = await self._wait_history(access, prompt_id)
            output_ref = self._output_ref(history, prompt_id, manifest)
            image = await self._fetch_image(access, output_ref)
            self._validate_image(image, manifest.capabilities)
            checks.extend(
                (
                    ValidationCheck("minimal_execution", "passed", "最小校验任务执行成功。"),
                    ValidationCheck("output_image", "passed", "输出图像格式和尺寸有效。"),
                )
            )
        except ComfyValidationError as error:
            checks.append(ValidationCheck(error.key, "failed", error.detail))
        cleanup_ok = await self._cleanup(access, uploaded, prompt_id)
        checks.append(
            ValidationCheck(
                "temporary_cleanup",
                "passed" if cleanup_ok else "failed",
                "远端校验临时文件已清理。" if cleanup_ok else "远端校验临时文件清理未确认。",
            )
        )
        return checks

    async def _wait_history(self, access: _Access, prompt_id: str) -> dict[str, object]:
        deadline = time.monotonic() + min(access.timeout, 30)
        while time.monotonic() < deadline:
            history = await self._json(access, "GET", f"/history/{prompt_id}")
            record = history.get(prompt_id)
            if isinstance(record, dict):
                status = cast(dict[str, object], record).get("status")
                if isinstance(status, dict):
                    state = cast(dict[str, object], status).get("status_str")
                    completed = cast(dict[str, object], status).get("completed")
                    if state in {"error", "failed"}:
                        raise ComfyValidationError("test_execution", "最小校验任务执行失败。")
                    if completed is True or state in {"success", "completed"}:
                        return history
            await asyncio.sleep(0.05)
        raise ComfyValidationError("test_timeout", "最小校验任务执行超时。")

    @staticmethod
    def _output_ref(
        history: dict[str, object], prompt_id: str, manifest: ParsedManifest
    ) -> dict[str, str]:
        record = history.get(prompt_id)
        record_map = cast(dict[str, object], record) if isinstance(record, dict) else {}
        if not isinstance(record_map.get("outputs"), dict):
            raise ComfyValidationError("test_output", "执行历史缺少输出。")
        outputs = cast(dict[str, object], record_map["outputs"])
        binding = manifest.outputs[0]
        node = outputs.get(binding.node_id)
        node_map = cast(dict[str, object], node) if isinstance(node, dict) else {}
        if not isinstance(node_map.get("images"), list):
            raise ComfyValidationError("test_output", "声明的输出节点未返回图像。")
        images = cast(list[object], node_map["images"])
        if binding.output_index >= len(images) or not isinstance(
            images[binding.output_index], dict
        ):
            raise ComfyValidationError("test_output", "声明的输出索引不存在。")
        raw = cast(dict[str, object], images[binding.output_index])
        result: dict[str, str] = {}
        for key in ("filename", "subfolder", "type"):
            value = raw.get(key, "")
            if not isinstance(value, str) or len(value) > 500:
                raise ComfyValidationError("test_output", "输出文件引用格式无效。")
            result[key] = value
        if not result["filename"] or result["type"] not in {"output", "temp"}:
            raise ComfyValidationError("test_output", "输出文件引用不受支持。")
        if ".." in result["filename"] or ".." in result["subfolder"]:
            raise ComfyValidationError("test_output", "输出文件引用不安全。")
        return result

    async def _fetch_image(self, access: _Access, ref: dict[str, str]) -> bytes:
        try:
            response = await self._client.get(
                f"{access.endpoint}/view",
                headers=access.headers,
                params=ref,
                timeout=access.timeout,
            )
        except Exception as error:
            raise ComfyValidationError("test_output", "校验输出下载失败。") from error
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if response.status_code != 200 or content_type not in {"image/png", "image/jpeg"}:
            raise ComfyValidationError("test_output", "校验输出响应无效。")
        if not response.content or len(response.content) > MAX_IMAGE_BYTES:
            raise ComfyValidationError("test_output", "校验输出大小无效。")
        return response.content

    @staticmethod
    def _validate_image(content: bytes, capabilities: dict[str, object]) -> None:
        constraints = capabilities.get("input_constraints")
        limits = cast(dict[str, object], constraints) if isinstance(constraints, dict) else {}
        max_width = limits.get("max_width", 4096)
        max_height = limits.get("max_height", 4096)
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
                width, height = image.size
        except (OSError, UnidentifiedImageError) as error:
            raise ComfyValidationError("test_output", "校验输出不是有效图像。") from error
        if (
            width < 1
            or height < 1
            or width > int(cast(int, max_width))
            or height > int(cast(int, max_height))
        ):
            raise ComfyValidationError("test_output", "校验输出尺寸超出 Workflow 声明范围。")

    async def _cleanup(self, access: _Access, uploaded: list[str], prompt_id: str | None) -> bool:
        if not uploaded and prompt_id is None:
            return True
        try:
            response = await self._client.request(
                "DELETE",
                f"{access.endpoint}/api/clothes-model/temp",
                headers=access.headers,
                json={"files": uploaded, "prompt_id": prompt_id},
                timeout=access.timeout,
            )
        except Exception:
            return False
        return response.status_code in {200, 204, 404}

    @staticmethod
    def _fixture_png() -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), color=(127, 127, 127)).save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _server_version(system: dict[str, object]) -> str | None:
        raw = system.get("system")
        value = (
            cast(dict[str, object], raw).get("comfyui_version")
            if isinstance(raw, dict)
            else None
        )
        return value[:160] if isinstance(value, str) else None

    @staticmethod
    def _check_metadata(
        workflow: dict[str, object], manifest: ParsedManifest, objects: dict[str, object]
    ) -> list[ValidationCheck]:
        checks: list[ValidationCheck] = []
        for node_id, raw_node in workflow.items():
            if not isinstance(raw_node, dict):
                continue
            node = cast(dict[str, object], raw_node)
            class_type = node.get("class_type")
            metadata = objects.get(class_type) if isinstance(class_type, str) else None
            if not isinstance(metadata, dict):
                checks.append(
                    ValidationCheck("required_node", "failed", f"节点类型 {class_type!s} 不可用。")
                )
                continue
            metadata_map = cast(dict[str, object], metadata)
            inputs_meta = metadata_map.get("input")
            if not isinstance(inputs_meta, dict):
                continue
            declared: set[str] = set()
            for group in ("required", "optional"):
                raw_group = cast(dict[str, object], inputs_meta).get(group)
                if isinstance(raw_group, dict):
                    declared.update(cast(dict[str, object], raw_group))
            for name, binding in manifest.bindings.items():
                if binding.node_id == node_id and declared and binding.input_name not in declared:
                    checks.append(
                        ValidationCheck(
                            "binding_input", "failed", f"绑定 {name} 的节点输入不可用。"
                        )
                    )
            inputs = node.get("inputs")
            if isinstance(inputs, dict):
                for input_name, current in cast(dict[str, object], inputs).items():
                    definition: object | None = None
                    for group in ("required", "optional"):
                        raw_group = cast(dict[str, object], inputs_meta).get(group)
                        if isinstance(raw_group, dict) and input_name in raw_group:
                            definition = cast(dict[str, object], raw_group)[input_name]
                    if (
                        isinstance(current, str)
                        and isinstance(definition, list)
                        and definition
                        and isinstance(definition[0], list)
                        and current not in cast(list[object], definition[0])
                    ):
                        checks.append(
                            ValidationCheck(
                                "required_model", "failed", "Workflow 声明的模型在节点上不可用。"
                            )
                        )
        return checks
