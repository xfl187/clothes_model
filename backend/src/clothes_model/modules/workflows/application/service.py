"""Immutable Workflow creation, structural validation, and redacted reads."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from clothes_model.infrastructure.storage import StorageError, WorkflowArtifactStorage
from clothes_model.modules.assets.domain import IdempotencyRecord
from clothes_model.modules.auth.domain import SecurityAuditEvent
from clothes_model.modules.comfy.domain import LOGICAL_COMFY_PROVIDER_ID
from clothes_model.modules.workflows.application.ports import WorkflowUnitOfWork
from clothes_model.modules.workflows.domain import (
    WorkflowStructureError,
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
    ) -> None:
        self._uow_factory = uow_factory
        self._artifacts = artifacts

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
        if entity.validation_json:
            raw_validation = cast(dict[str, Any], json.loads(entity.validation_json))
            raw_messages = raw_validation.get("messages")
            if isinstance(raw_messages, list):
                messages = [str(item)[:500] for item in cast(list[object], raw_messages)]
        return {
            "id": entity.id,
            "workflow_id": entity.workflow_id,
            "version": entity.version,
            "mode": entity.mode,
            "state": entity.state,
            "capabilities": capabilities,
            "logical_provider_ref": {
                "provider_id": LOGICAL_COMFY_PROVIDER_ID,
                "config_version_id": "00000000-0000-4000-8000-000000000006",
                "revision": 1,
            },
            "artifacts": {
                "workflow_sha256": entity.workflow_sha256,
                "manifest_sha256": entity.manifest_sha256,
                "workflow_size_bytes": len(workflow_bytes),
                "manifest_size_bytes": len(manifest_bytes),
                "bindings_schema_version": entity.bindings_schema_version,
            },
            "manifest_summary": parsed.summary(),
            "validation_status": (
                "not_run" if entity.validated_at is None else "passed"
            ),
            "validation_messages": messages,
            "created_at": entity.created_at,
            "validated_at": entity.validated_at,
            "activated_at": entity.activated_at,
            "retired_at": entity.retired_at,
        }
