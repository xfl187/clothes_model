import json
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import ValidationError

from clothes_model.core.features import require_feature
from clothes_model.core.problems import AppProblem
from clothes_model.generated.models import (
    WorkflowActivateRequest,
    WorkflowCreateRequest,
    WorkflowRetireRequest,
)
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.modules.auth.http import AdminIdentity, require_admin
from clothes_model.modules.comfy.application import ComfyWorkflowValidator
from clothes_model.modules.workflows.application import WorkflowService, WorkflowServiceError

async def _require_comfyui(request: Request) -> None:
    require_feature(request, "comfyui")


router = APIRouter(tags=["Workflows"], dependencies=[Depends(_require_comfyui)])


def _service(request: Request) -> WorkflowService:
    uow_factory = lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions)  # noqa: E731
    return WorkflowService(
        uow_factory,
        request.app.state.workflow_artifacts,
        ComfyWorkflowValidator(
            uow_factory,
            request.app.state.secret_cipher,
            request.app.state.comfy_http_client,
        ),
    )


def _problem(error: WorkflowServiceError) -> AppProblem:
    return AppProblem(error.status, error.code, "Workflow 请求失败", error.detail)


def _load_without_duplicate_keys(raw: bytes) -> dict[str, object]:
    if not raw or len(raw) > 4_100_000:
        raise WorkflowServiceError("workflow_request_size_invalid", "请求体大小无效。", status=422)

    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise WorkflowServiceError(
                    "workflow_json_duplicate_key", "Workflow 请求包含重复 JSON 键。", status=422
                )
            value[key] = item
        return value

    try:
        decoded: object = json.loads(raw, object_pairs_hook=object_pairs)
    except WorkflowServiceError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowServiceError(
            "workflow_request_invalid", "Workflow 请求不是有效 JSON。", status=422
        ) from error
    if not isinstance(decoded, dict):
        raise WorkflowServiceError(
            "workflow_request_invalid", "Workflow 请求必须是 JSON 对象。", status=422
        )
    return cast(dict[str, object], decoded)


@router.get("/api/v1/admin/workflows", operation_id="listWorkflowVersions")
async def list_workflows(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, object]:
    del identity
    service = _service(request)
    try:
        items = [service.payload(item) for item in await service.list(limit)]
    except WorkflowServiceError as error:
        raise _problem(error) from error
    return {"items": items, "next_cursor": None, "has_more": False}


@router.post(
    "/api/v1/admin/workflows",
    operation_id="createWorkflowVersion",
    status_code=201,
)
async def create_workflow(
    request: Request,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    service = _service(request)
    try:
        decoded = _load_without_duplicate_keys(await request.body())
        body = WorkflowCreateRequest.model_validate(decoded)
        entity = await service.create(
            workflow_id=body.workflow_id,
            version=body.version,
            mode=body.mode.value,
            workflow_json=body.workflow_json,
            manifest=body.manifest,
            actor_id=identity.token_id,
            idempotency_key=idempotency_key,
        )
        return service.payload(entity)
    except ValidationError as error:
        raise AppProblem(
            422,
            "workflow_request_invalid",
            "Workflow 请求失败",
            "Workflow 请求字段无效。",
        ) from error
    except WorkflowServiceError as error:
        raise _problem(error) from error


@router.get(
    "/api/v1/admin/workflows/{workflow_version_id}",
    operation_id="getWorkflowVersion",
)
async def get_workflow(
    request: Request,
    workflow_version_id: str,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
) -> dict[str, object]:
    del identity
    service = _service(request)
    entity = await service.get(workflow_version_id)
    if entity is None:
        raise AppProblem(404, "not_found", "Workflow 不存在", "Workflow 版本不存在。")
    try:
        return service.payload(entity)
    except WorkflowServiceError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/admin/workflows/{workflow_version_id}/validate",
    operation_id="validateWorkflowVersion",
)
async def validate_workflow(
    request: Request,
    workflow_version_id: str,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    try:
        return await _service(request).validate(
            version_id=workflow_version_id,
            actor_id=identity.token_id,
            idempotency_key=idempotency_key,
        )
    except WorkflowServiceError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/admin/workflows/{workflow_version_id}/activate",
    operation_id="activateWorkflowVersion",
)
async def activate_workflow(
    request: Request,
    workflow_version_id: str,
    body: WorkflowActivateRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    try:
        entity = await _service(request).activate(
            version_id=workflow_version_id,
            expected_current_id=(
                str(body.expected_current_active_workflow_version_id)
                if body.expected_current_active_workflow_version_id
                else None
            ),
            reason=body.reason,
            actor_id=identity.token_id,
            idempotency_key=idempotency_key,
        )
        return _service(request).payload(entity)
    except WorkflowServiceError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/admin/workflows/{workflow_version_id}/retire",
    operation_id="retireWorkflowVersion",
)
async def retire_workflow(
    request: Request,
    workflow_version_id: str,
    body: WorkflowRetireRequest,
    identity: Annotated[AdminIdentity, Depends(require_admin)],
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    try:
        entity = await _service(request).retire(
            version_id=workflow_version_id,
            reason=body.reason,
            actor_id=identity.token_id,
            idempotency_key=idempotency_key,
        )
        return _service(request).payload(entity)
    except WorkflowServiceError as error:
        raise _problem(error) from error
