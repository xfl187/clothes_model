"""Immutable Workflow creation, structural validation, and redacted reads."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
from uuid import uuid4

from clothes_model.infrastructure.storage import StorageError, WorkflowArtifactStorage
from clothes_model.modules.assets.domain import IdempotencyRecord
from clothes_model.modules.auth.domain import SecurityAuditEvent
from clothes_model.modules.comfy.application import ComfyWorkflowValidator
from clothes_model.modules.comfy.domain import LOGICAL_COMFY_PROVIDER_ID
from clothes_model.modules.providers.domain import ProviderConfigRevision
from clothes_model.modules.workflows.application.ports import WorkflowUnitOfWork
from clothes_model.modules.workflows.domain import (
    ParsedManifest,
    WorkflowStructureError,
    WorkflowValidationRun,
    WorkflowVersion,
    parse_manifest,
)

MAX_WORKFLOW_BYTES = 2_000_000
MAX_JSON_DEPTH = 40


class WorkflowServiceError(RuntimeError):
    def __init__(self, code: str, detail: str, *, status: int = 409) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def canonical_json(value: object) -> bytes:
    _check_depth(value, 0)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise WorkflowServiceError(
            "workflow_json_invalid", "Workflow JSON 包含不可序列化或非有限值。", status=422
        ) from error
    if len(encoded) > MAX_WORKFLOW_BYTES:
        raise WorkflowServiceError(
            "workflow_json_too_large", "Workflow JSON 超过安全上限。", status=422
        )
    return encoded


def _check_depth(value: object, depth: int) -> None:
    if depth > MAX_JSON_DEPTH:
        raise WorkflowServiceError(
            "workflow_json_too_deep", "Workflow JSON 嵌套层级超过安全上限。", status=422
        )
    if isinstance(value, dict):
        for item in cast(dict[object, object], value).values():
            _check_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in cast(list[object], value):
            _check_depth(item, depth + 1)


class WorkflowService:
    def __init__(
        self,
        uow_factory: Callable[[], WorkflowUnitOfWork],
        artifacts: WorkflowArtifactStorage,
        validator: ComfyWorkflowValidator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._artifacts = artifacts
        self._validator = validator

    async def create(
        self,
        *,
        workflow_id: str,
        version: int,
        mode: str,
        workflow_json: dict[str, object],
        manifest: dict[str, object],
        actor_id: str,
        idempotency_key: str,
    ) -> WorkflowVersion:
        if not workflow_id.strip() or len(workflow_id) > 100 or version < 1:
            raise WorkflowServiceError(
                "workflow_identity_invalid", "Workflow 标识或版本无效。", status=422
            )
        if mode != "precise_try_on":
            raise WorkflowServiceError("workflow_mode_invalid", "Workflow 模式无效。", status=422)
        workflow_bytes = canonical_json(workflow_json)
        manifest_bytes = canonical_json(manifest)
        workflow_digest = hashlib.sha256(workflow_bytes).hexdigest()
        manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
        try:
            parsed = parse_manifest(manifest, workflow_json)
        except WorkflowStructureError as error:
            raise WorkflowServiceError(error.code, error.detail, status=422) from error
        request_digest = hashlib.sha256(
            canonical_json(
                {
                    "workflow_id": workflow_id,
                    "version": version,
                    "mode": mode,
                    "workflow_sha256": workflow_digest,
                    "manifest_sha256": manifest_digest,
                }
            )
        ).hexdigest()
        key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        async with self._uow_factory() as uow:
            replay = await uow.idempotency.get_bound(
                "admin", actor_id, "workflow.create", key_digest
            )
            if replay is not None:
                if replay.request_digest != request_digest:
                    raise WorkflowServiceError(
                        "idempotency_key_reused", "幂等键已绑定到不同 Workflow 请求。"
                    )
                existing = await uow.workflows.get(str(replay.resource_id))
                if existing is None:
                    raise WorkflowServiceError(
                        "idempotency_resource_missing", "幂等记录指向的 Workflow 不存在。"
                    )
                return existing
            existing = await uow.workflows.get_by_identity(workflow_id, version)
            if existing is not None:
                if (
                    existing.workflow_sha256 == workflow_digest
                    and existing.manifest_sha256 == manifest_digest
                ):
                    return existing
                raise WorkflowServiceError(
                    "workflow_version_conflict", "同一 Workflow 版本已存在但内容不同。"
                )

        version_id = str(uuid4())
        try:
            stored = self._artifacts.publish(version_id, workflow_bytes, manifest_bytes)
        except (OSError, StorageError) as error:
            raise WorkflowServiceError(
                "workflow_storage_failed", "Workflow 制品无法安全写入。", status=507
            ) from error
        timestamp = datetime.now(UTC)
        entity = WorkflowVersion(
            id=version_id,
            workflow_id=workflow_id,
            version=version,
            mode=mode,
            display_name=workflow_id,
            state="draft",
            workflow_sha256=workflow_digest,
            workflow_path=stored.workflow_path,
            manifest_sha256=manifest_digest,
            manifest_path=stored.manifest_path,
            bindings_schema_version=parsed.schema_version,
            manifest_json=manifest_bytes.decode("utf-8"),
            capabilities_json=json.dumps(
                parsed.capabilities, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
            created_at=timestamp,
        )
        try:
            async with self._uow_factory() as uow:
                await uow.workflows.add(entity)
                await uow.idempotency.add(
                    IdempotencyRecord(
                        id=str(uuid4()),
                        actor_scope="admin",
                        actor_id=actor_id,
                        operation="workflow.create",
                        key_digest=key_digest,
                        request_digest=request_digest,
                        state="completed",
                        response_status=201,
                        response_body=json.dumps({"id": version_id}, separators=(",", ":")),
                        resource_id=version_id,
                        created_at=timestamp,
                        expires_at=timestamp + timedelta(days=7),
                    )
                )
                await uow.security_audit.add(
                    SecurityAuditEvent(
                        id=str(uuid4()),
                        action="workflow.created",
                        actor_kind="admin_session",
                        actor_id=actor_id,
                        outcome="succeeded",
                        context_json=json.dumps(
                            {
                                "workflow_id": workflow_id,
                                "version": version,
                                "workflow_sha256": workflow_digest,
                                "manifest_sha256": manifest_digest,
                            },
                            separators=(",", ":"),
                        ),
                        created_at=timestamp,
                    )
                )
                await uow.commit()
        except Exception as error:
            self._artifacts.delete_version(version_id)
            if isinstance(error, WorkflowServiceError):
                raise
            raise WorkflowServiceError(
                "workflow_persistence_failed", "Workflow 元数据无法提交。"
            ) from error
        return entity

    async def get(self, version_id: str) -> WorkflowVersion | None:
        async with self._uow_factory() as uow:
            return await uow.workflows.get(version_id)

    async def list(self, limit: int = 100) -> list[WorkflowVersion]:
        async with self._uow_factory() as uow:
            return await uow.workflows.list_all(limit)

    async def validate(
        self, *, version_id: str, actor_id: str, idempotency_key: str
    ) -> dict[str, object]:
        if self._validator is None:
            raise WorkflowServiceError("workflow_validator_unavailable", "Workflow 校验器不可用。")
        key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        request_digest = hashlib.sha256(f"validate:{version_id}".encode()).hexdigest()
        async with self._uow_factory() as uow:
            replay = await uow.idempotency.get_bound(
                "admin", actor_id, "workflow.validate", key_digest
            )
            if replay is not None:
                if replay.request_digest != request_digest:
                    raise WorkflowServiceError("idempotency_key_reused", "幂等键已绑定到其他请求。")
                if replay.response_body is None:
                    raise WorkflowServiceError(
                        "idempotency_response_missing", "幂等响应记录缺失。"
                    )
                decoded: object = json.loads(replay.response_body)
                return cast(dict[str, object], decoded)
            entity = await uow.workflows.get(version_id)
        if entity is None:
            raise WorkflowServiceError("not_found", "Workflow 版本不存在。", status=404)
        workflow, manifest = self._read_parsed(entity)
        result = await self._validator.validate(workflow, manifest)
        timestamp = datetime.now(UTC)
        checks = [item.payload() for item in result.checks]
        compatibility_status = (
            "compatible"
            if result.status == "passed"
            else "offline"
            if result.status == "offline"
            else "incompatible"
        )
        response: dict[str, object] = {
            "status": "passed" if result.status == "passed" else "failed",
            "checked_at": timestamp,
            "checks": checks,
            "compatibility": {
                "status": compatibility_status,
                "checked_at": timestamp,
                "observed_server_version": result.server_version,
                "checks": checks,
            },
        }
        persisted_response = self._json_ready(response)
        validation = {
            "status": result.status,
            "messages": [item.detail for item in result.checks if item.status != "passed"],
            "checks": checks,
            "checked_at": timestamp.isoformat(),
            "node_fingerprint": result.node_fingerprint,
            "observed_server_version": result.server_version,
        }
        updated = replace(
            entity,
            validation_json=json.dumps(validation, ensure_ascii=False, separators=(",", ":")),
            validated_at=timestamp if result.status == "passed" else entity.validated_at,
        )
        async with self._uow_factory() as uow:
            await uow.workflows.update_lifecycle(updated)
            await uow.workflows.add_validation(
                WorkflowValidationRun(
                    id=str(uuid4()),
                    workflow_version_id=version_id,
                    status=cast(Any, result.status),
                    result_json=json.dumps(validation, ensure_ascii=False, separators=(",", ":")),
                    checked_node_fingerprint=result.node_fingerprint,
                    created_at=timestamp,
                )
            )
            await self._audit(
                uow,
                action="workflow.validated",
                actor_id=actor_id,
                outcome="succeeded" if result.status == "passed" else "failed",
                context={"workflow_version_id": version_id, "status": result.status},
                timestamp=timestamp,
            )
            await self._record_idempotency(
                uow,
                actor_id=actor_id,
                operation="workflow.validate",
                key_digest=key_digest,
                request_digest=request_digest,
                resource_id=version_id,
                response_body=persisted_response,
                timestamp=timestamp,
            )
            await uow.commit()
        return response

    async def activate(
        self,
        *,
        version_id: str,
        expected_current_id: str | None,
        reason: str | None,
        actor_id: str,
        idempotency_key: str,
    ) -> WorkflowVersion:
        request = {
            "version_id": version_id,
            "expected_current_id": expected_current_id,
            "reason": reason,
        }
        key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        request_digest = hashlib.sha256(canonical_json(request)).hexdigest()
        timestamp = datetime.now(UTC)
        try:
            async with self._uow_factory() as uow:
                replay = await uow.idempotency.get_bound(
                    "admin", actor_id, "workflow.activate", key_digest
                )
                if replay is not None:
                    if replay.request_digest != request_digest:
                        raise WorkflowServiceError(
                            "idempotency_key_reused", "幂等键已绑定到其他请求。"
                        )
                    existing = await uow.workflows.get(str(replay.resource_id))
                    if existing is None:
                        raise WorkflowServiceError(
                            "idempotency_resource_missing", "幂等记录指向的 Workflow 不存在。"
                        )
                    return existing
                target = await uow.workflows.get(version_id)
                if target is None:
                    raise WorkflowServiceError("not_found", "Workflow 版本不存在。", status=404)
                validation = self._validation(target)
                if target.validated_at is None or validation.get("status") != "passed":
                    raise WorkflowServiceError(
                        "workflow_not_validated", "Workflow 必须先通过当前节点的在线校验。"
                    )
                current = await uow.workflows.get_active(target.mode)
                if expected_current_id is not None and (
                    current is None or current.id != expected_current_id
                ):
                    raise WorkflowServiceError(
                        "workflow_active_version_changed", "当前激活版本与乐观锁条件不一致。"
                    )
                if current is not None and current.id == target.id:
                    return current
                if current is not None:
                    await uow.workflows.update_lifecycle(
                        replace(current, state="retired", retired_at=timestamp)
                    )
                provider = await uow.provider_configs.get_config(LOGICAL_COMFY_PROVIDER_ID)
                current_revision = await uow.provider_configs.get_current_revision(
                    LOGICAL_COMFY_PROVIDER_ID
                )
                if provider is None or current_revision is None:
                    raise WorkflowServiceError(
                        "logical_provider_missing", "逻辑 Comfy Provider 配置不存在。"
                    )
                revision = ProviderConfigRevision(
                    id=str(uuid4()),
                    provider_id=LOGICAL_COMFY_PROVIDER_ID,
                    revision=current_revision.revision + 1,
                    adapter_type="comfyui",
                    endpoint="comfy://physical-node",
                    model=f"{target.workflow_id}:{target.version}",
                    timeout_seconds=current_revision.timeout_seconds,
                    capabilities_json=target.capabilities_json,
                    vendor_parameters_json=json.dumps(
                        {
                            "workflow_version_id": target.id,
                            "workflow_sha256": target.workflow_sha256,
                            "manifest_sha256": target.manifest_sha256,
                            "bindings_schema_version": target.bindings_schema_version,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    created_at=timestamp,
                )
                validation["logical_provider_ref"] = {
                    "provider_id": LOGICAL_COMFY_PROVIDER_ID,
                    "config_version_id": revision.id,
                    "revision": revision.revision,
                }
                activated = replace(
                    target,
                    state="active",
                    activated_at=timestamp,
                    retired_at=None,
                    validation_json=json.dumps(
                        validation, ensure_ascii=False, separators=(",", ":")
                    ),
                )
                await uow.provider_configs.add_revision(revision)
                await uow.provider_configs.update_config(
                    replace(provider, state="active", updated_at=timestamp)
                )
                await uow.workflows.update_lifecycle(activated)
                await self._audit(
                    uow,
                    action="workflow.activated",
                    actor_id=actor_id,
                    outcome="succeeded",
                    context={"workflow_version_id": target.id, "reason": (reason or "")[:500]},
                    timestamp=timestamp,
                )
                await self._record_idempotency(
                    uow,
                    actor_id=actor_id,
                    operation="workflow.activate",
                    key_digest=key_digest,
                    request_digest=request_digest,
                    resource_id=version_id,
                    response_body=json.dumps({"id": version_id}, separators=(",", ":")),
                    timestamp=timestamp,
                )
                await uow.commit()
                return activated
        except WorkflowServiceError:
            raise
        except Exception as error:
            raise WorkflowServiceError(
                "workflow_activation_conflict", "Workflow 激活发生并发冲突，请重试。"
            ) from error

    async def retire(
        self,
        *,
        version_id: str,
        reason: str | None,
        actor_id: str,
        idempotency_key: str,
    ) -> WorkflowVersion:
        request = {"version_id": version_id, "reason": reason}
        key_digest = hashlib.sha256(idempotency_key.encode()).hexdigest()
        request_digest = hashlib.sha256(canonical_json(request)).hexdigest()
        timestamp = datetime.now(UTC)
        async with self._uow_factory() as uow:
            replay = await uow.idempotency.get_bound(
                "admin", actor_id, "workflow.retire", key_digest
            )
            if replay is not None:
                if replay.request_digest != request_digest:
                    raise WorkflowServiceError("idempotency_key_reused", "幂等键已绑定到其他请求。")
                existing = await uow.workflows.get(str(replay.resource_id))
                if existing is None:
                    raise WorkflowServiceError(
                        "idempotency_resource_missing", "幂等记录指向的 Workflow 不存在。"
                    )
                return existing
            target = await uow.workflows.get(version_id)
            if target is None:
                raise WorkflowServiceError("not_found", "Workflow 版本不存在。", status=404)
            if target.state == "retired":
                return target
            if target.state != "active":
                raise WorkflowServiceError(
                    "workflow_not_active", "只有已激活 Workflow 可以退役。"
                )
            retired = replace(target, state="retired", retired_at=timestamp)
            await uow.workflows.update_lifecycle(retired)
            await self._audit(
                uow,
                action="workflow.retired",
                actor_id=actor_id,
                outcome="succeeded",
                context={"workflow_version_id": version_id, "reason": (reason or "")[:500]},
                timestamp=timestamp,
            )
            await self._record_idempotency(
                uow,
                actor_id=actor_id,
                operation="workflow.retire",
                key_digest=key_digest,
                request_digest=request_digest,
                resource_id=version_id,
                response_body=json.dumps({"id": version_id}, separators=(",", ":")),
                timestamp=timestamp,
            )
            await uow.commit()
            return retired

    def _read_parsed(
        self, entity: WorkflowVersion
    ) -> tuple[dict[str, object], ParsedManifest]:
        workflow_bytes = self._artifacts.read(entity.workflow_path)
        manifest_bytes = self._artifacts.read(entity.manifest_path)
        if hashlib.sha256(workflow_bytes).hexdigest() != entity.workflow_sha256:
            raise WorkflowServiceError("workflow_artifact_corrupt", "Workflow 制品校验失败。")
        if hashlib.sha256(manifest_bytes).hexdigest() != entity.manifest_sha256:
            raise WorkflowServiceError("workflow_artifact_corrupt", "Manifest 制品校验失败。")
        workflow = cast(dict[str, object], json.loads(workflow_bytes))
        manifest = cast(dict[str, object], json.loads(manifest_bytes))
        return workflow, parse_manifest(manifest, workflow)

    @staticmethod
    def _validation(entity: WorkflowVersion) -> dict[str, Any]:
        if not entity.validation_json:
            return {}
        decoded: object = json.loads(entity.validation_json)
        return cast(dict[str, Any], decoded) if isinstance(decoded, dict) else {}

    @staticmethod
    def _json_ready(value: dict[str, object]) -> str:
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))

    @staticmethod
    async def _audit(
        uow: WorkflowUnitOfWork,
        *,
        action: str,
        actor_id: str,
        outcome: Literal["succeeded", "failed", "denied"],
        context: dict[str, object],
        timestamp: datetime,
    ) -> None:
        await uow.security_audit.add(
            SecurityAuditEvent(
                id=str(uuid4()),
                action=action,
                actor_kind="admin_session",
                actor_id=actor_id,
                outcome=outcome,
                context_json=json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                created_at=timestamp,
            )
        )

    @staticmethod
    async def _record_idempotency(
        uow: WorkflowUnitOfWork,
        *,
        actor_id: str,
        operation: str,
        key_digest: str,
        request_digest: str,
        resource_id: str,
        response_body: str,
        timestamp: datetime,
    ) -> None:
        await uow.idempotency.add(
            IdempotencyRecord(
                id=str(uuid4()),
                actor_scope="admin",
                actor_id=actor_id,
                operation=operation,
                key_digest=key_digest,
                request_digest=request_digest,
                state="completed",
                response_status=200,
                response_body=response_body,
                resource_id=resource_id,
                created_at=timestamp,
                expires_at=timestamp + timedelta(days=7),
            )
        )

    def payload(self, entity: WorkflowVersion) -> dict[str, object]:
        workflow_bytes = self._artifacts.read(entity.workflow_path)
        manifest_bytes = self._artifacts.read(entity.manifest_path)
        if hashlib.sha256(workflow_bytes).hexdigest() != entity.workflow_sha256:
            raise WorkflowServiceError("workflow_artifact_corrupt", "Workflow 制品校验失败。")
        if hashlib.sha256(manifest_bytes).hexdigest() != entity.manifest_sha256:
            raise WorkflowServiceError("workflow_artifact_corrupt", "Manifest 制品校验失败。")
        manifest = cast(dict[str, object], json.loads(entity.manifest_json))
        capabilities = cast(dict[str, object], json.loads(entity.capabilities_json))
        parsed = parse_manifest(manifest, cast(dict[str, object], json.loads(workflow_bytes)))
        messages: list[str] = []
        validation_status = "not_run"
        logical_provider_ref: dict[str, object] = {
            "provider_id": LOGICAL_COMFY_PROVIDER_ID,
            "config_version_id": "00000000-0000-4000-8000-000000000006",
            "revision": 1,
        }
        if entity.validation_json:
            raw_validation = cast(dict[str, Any], json.loads(entity.validation_json))
            validation_status = "passed" if raw_validation.get("status") == "passed" else "failed"
            raw_messages = raw_validation.get("messages")
            if isinstance(raw_messages, list):
                messages = [str(item)[:500] for item in cast(list[object], raw_messages)]
            raw_ref = raw_validation.get("logical_provider_ref")
            if isinstance(raw_ref, dict):
                logical_provider_ref = cast(dict[str, object], raw_ref)
        return {
            "id": entity.id,
            "workflow_id": entity.workflow_id,
            "version": entity.version,
            "mode": entity.mode,
            "state": entity.state,
            "capabilities": capabilities,
            "logical_provider_ref": logical_provider_ref,
            "artifacts": {
                "workflow_sha256": entity.workflow_sha256,
                "manifest_sha256": entity.manifest_sha256,
                "workflow_size_bytes": len(workflow_bytes),
                "manifest_size_bytes": len(manifest_bytes),
                "bindings_schema_version": entity.bindings_schema_version,
            },
            "manifest_summary": parsed.summary(),
            "validation_status": validation_status,
            "validation_messages": messages,
            "created_at": entity.created_at,
            "validated_at": entity.validated_at,
            "activated_at": entity.activated_at,
            "retired_at": entity.retired_at,
        }
