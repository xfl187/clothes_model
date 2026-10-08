"""V1.1 layered-outfit HTTP surface."""

import shutil
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from clothes_model.core.features import require_feature
from clothes_model.core.problems import AppProblem
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.modules.auth.application import VerifiedCredential
from clothes_model.modules.auth.http import require_app
from clothes_model.modules.outfits.application.service import OutfitError, OutfitService
from clothes_model.modules.providers.application.services import ProviderConfigService

async def _require_layered_outfits(request: Request) -> None:
    require_feature(request, "layered_outfits")


router = APIRouter(tags=["Outfits"], dependencies=[Depends(_require_layered_outfits)])
AppIdentity = Annotated[VerifiedCredential, Depends(require_app)]
LayerRoleLiteral = Literal["inner_top", "outerwear", "lower_body", "dress"]


class CreateSessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_asset_id: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)


class UpdateSessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=120)
    favorite: bool | None = None


class CreateBranchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=120)
    base_revision_id: str | None = None
    route: Literal["split", "dress"] | None = None


class UpdateBranchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=120)
    favorite: bool | None = None
    mainline: bool | None = None


class AddLayerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: LayerRoleLiteral
    garment_asset_id: str = Field(min_length=1)
    provider_id: str | None = None
    candidate_count: int = Field(default=1, ge=1, le=4)
    mask_asset_id: str | None = None


class SelectRevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_item_id: str = Field(min_length=1)
    output_id: str = Field(min_length=1)


class RemoveLayerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["remove", "revert"] = "remove"


class SwitchRouteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: Literal["split", "dress"]


class ReapplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str | None = None
    candidate_count: int = Field(default=1, ge=1, le=4)


def _service(request: Request) -> OutfitService:
    return OutfitService(lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions))


def _provider_service(request: Request) -> ProviderConfigService:
    return ProviderConfigService(
        lambda: SqlAlchemyUnitOfWork(request.app.state.database.sessions),
        request.app.state.provider_registry,
        request.app.state.secret_cipher,
    )


def _capacity(request: Request) -> bool:
    usage = shutil.disk_usage(request.app.state.storage.root)
    return usage.free - request.app.state.settings.storage_reserve_bytes > 0


def _problem(error: OutfitError) -> AppProblem:
    return AppProblem(error.status, error.code, "穿搭操作失败", error.detail)


@router.get("/api/v1/outfits", operation_id="listOutfitSessions")
async def list_outfit_sessions(
    request: Request,
    identity: AppIdentity,
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, object]:
    return await _service(request).list_sessions(
        owner_scope_id=identity.owner_scope_id, limit=limit
    )


@router.post("/api/v1/outfits", status_code=201, operation_id="createOutfitSession")
async def create_outfit_session(
    request: Request,
    body: CreateSessionBody,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    try:
        return await _service(request).create_session(
            owner_scope_id=identity.owner_scope_id,
            person_asset_id=body.person_asset_id,
            name=body.name,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.get("/api/v1/outfits/{session_id}", operation_id="getOutfitSession")
async def get_outfit_session(
    request: Request,
    session_id: str,
    identity: AppIdentity,
) -> dict[str, object]:
    try:
        return await _service(request).get_session(
            session_id=session_id, owner_scope_id=identity.owner_scope_id
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.patch("/api/v1/outfits/{session_id}", operation_id="updateOutfitSession")
async def update_outfit_session(
    request: Request,
    session_id: str,
    body: UpdateSessionBody,
    identity: AppIdentity,
) -> dict[str, object]:
    try:
        return await _service(request).update_session(
            session_id=session_id,
            owner_scope_id=identity.owner_scope_id,
            name=body.name,
            favorite=body.favorite,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.delete("/api/v1/outfits/{session_id}", status_code=204, operation_id="deleteOutfitSession")
async def delete_outfit_session(
    request: Request,
    session_id: str,
    identity: AppIdentity,
) -> None:
    try:
        await _service(request).delete_session(
            session_id=session_id, owner_scope_id=identity.owner_scope_id
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/outfits/{session_id}/branches",
    status_code=201,
    operation_id="createOutfitBranch",
)
async def create_outfit_branch(
    request: Request,
    session_id: str,
    identity: AppIdentity,
    body: CreateBranchBody | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    try:
        return await _service(request).create_branch(
            session_id=session_id,
            owner_scope_id=identity.owner_scope_id,
            name=body.name if body else None,
            route=body.route if body else None,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.patch(
    "/api/v1/outfits/{session_id}/branches/{branch_id}",
    operation_id="updateOutfitBranch",
)
async def update_outfit_branch(
    request: Request,
    session_id: str,
    branch_id: str,
    body: UpdateBranchBody,
    identity: AppIdentity,
) -> dict[str, object]:
    try:
        return await _service(request).update_branch(
            session_id=session_id,
            branch_id=branch_id,
            owner_scope_id=identity.owner_scope_id,
            name=body.name,
            favorite=body.favorite,
            mainline=body.mainline,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.delete(
    "/api/v1/outfits/{session_id}/branches/{branch_id}",
    operation_id="deleteOutfitBranch",
)
async def delete_outfit_branch(
    request: Request,
    session_id: str,
    branch_id: str,
    identity: AppIdentity,
) -> dict[str, object]:
    try:
        return await _service(request).delete_branch(
            session_id=session_id,
            branch_id=branch_id,
            owner_scope_id=identity.owner_scope_id,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/outfits/{session_id}/branches/{branch_id}/layers",
    status_code=201,
    operation_id="addOutfitLayer",
)
async def add_outfit_layer(
    request: Request,
    session_id: str,
    branch_id: str,
    body: AddLayerBody,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    provider_service = _provider_service(request)
    provider_id = body.provider_id
    if provider_id is None:
        selection = await provider_service.get_default()
        if selection is None:
            raise AppProblem(409, "provider_not_usable", "穿搭操作失败", "尚未设置默认 Provider。")
        provider_id = selection.provider_id
    try:
        return await _service(request).add_layer(
            session_id=session_id,
            branch_id=branch_id,
            owner_scope_id=identity.owner_scope_id,
            provider_service=provider_service,
            capacity=lambda: _capacity(request),
            role=body.role,
            garment_asset_id=body.garment_asset_id,
            provider_id=provider_id,
            candidate_count=body.candidate_count,
            mask_asset_id=body.mask_asset_id,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/outfits/{session_id}/branches/{branch_id}/revisions/{revision_id}/select",
    operation_id="selectOutfitRevision",
)
async def select_outfit_revision(
    request: Request,
    session_id: str,
    branch_id: str,
    revision_id: str,
    body: SelectRevisionBody,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    try:
        return await _service(request).select_revision(
            session_id=session_id,
            branch_id=branch_id,
            revision_id=revision_id,
            owner_scope_id=identity.owner_scope_id,
            job_item_id=body.job_item_id,
            output_id=body.output_id,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.delete(
    "/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}",
    operation_id="removeOutfitLayer",
)
async def remove_outfit_layer(
    request: Request,
    session_id: str,
    branch_id: str,
    layer_id: str,
    identity: AppIdentity,
    body: RemoveLayerBody | None = None,
) -> dict[str, object]:
    try:
        return await _service(request).remove_layer(
            session_id=session_id,
            branch_id=branch_id,
            layer_id=layer_id,
            owner_scope_id=identity.owner_scope_id,
            mode=body.mode if body else "remove",
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/outfits/{session_id}/route",
    operation_id="switchOutfitRoute",
)
async def switch_outfit_route(
    request: Request,
    session_id: str,
    body: SwitchRouteBody,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    try:
        return await _service(request).switch_route(
            session_id=session_id,
            owner_scope_id=identity.owner_scope_id,
            route=body.route,
        )
    except OutfitError as error:
        raise _problem(error) from error


@router.post(
    "/api/v1/outfits/{session_id}/branches/{branch_id}/layers/{layer_id}/reapply",
    status_code=201,
    operation_id="reapplyOutfitLayer",
)
async def reapply_outfit_layer(
    request: Request,
    session_id: str,
    branch_id: str,
    layer_id: str,
    body: ReapplyBody,
    identity: AppIdentity,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    del idempotency_key
    try:
        return await _service(request).reapply_layer(
            session_id=session_id,
            branch_id=branch_id,
            layer_id=layer_id,
            owner_scope_id=identity.owner_scope_id,
            provider_service=_provider_service(request),
            capacity=lambda: _capacity(request),
            provider_id=body.provider_id,
            candidate_count=body.candidate_count,
        )
    except OutfitError as error:
        raise _problem(error) from error
