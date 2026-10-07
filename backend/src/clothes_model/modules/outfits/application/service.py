"""V1.1 layered-outfit application service."""

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork
from clothes_model.modules.assets.domain import AssetReference
from clothes_model.modules.jobs.domain import Job, JobItem, JobPersonInput
from clothes_model.modules.jobs.infrastructure.workflow_lock import (
    WorkflowLockError,
    lock_active_workflow,
)
from clothes_model.modules.jobs.payloads import job_payload
from clothes_model.modules.outfits.domain import (
    DEFAULT_LAYER_DEFINITION_VERSION,
    LayerTypeDefinition,
    OutfitBranch,
    OutfitLayer,
    OutfitRevision,
    OutfitSession,
)
from clothes_model.modules.providers.application.services import ProviderConfigService

DEFAULT_ROUTE = "split"
TERMINAL_JOB_STATES = ("succeeded", "partially_succeeded", "failed", "cancelled")


class OutfitError(Exception):
    def __init__(self, status: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


class OutfitService:
    def __init__(self, uow_factory: Callable[[], SqlAlchemyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def create_session(
        self, *, owner_scope_id: str | None, person_asset_id: str, name: str | None
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            person = await uow.assets.get(person_asset_id)
            if person is None or person.kind != "person" or person.content_state != "available":
                raise OutfitError(422, "invalid_person_asset", "需要一张可用的人物素材。")
            session_id, branch_id = str(uuid4()), str(uuid4())
            root_revision_id = str(uuid4())
            session = OutfitSession(
                id=session_id,
                owner_scope_id=owner_scope_id,
                name=(name or "分层穿搭").strip() or "分层穿搭",
                favorite=False,
                person_asset_id=person_asset_id,
                layer_definition_version=DEFAULT_LAYER_DEFINITION_VERSION,
                main_branch_id=branch_id,
                created_at=now,
                updated_at=now,
            )
            await uow.outfits.add_session(session)
            await uow.outfits.add_branch(
                OutfitBranch(
                    id=branch_id,
                    session_id=session_id,
                    name="主线",
                    route=DEFAULT_ROUTE,
                    favorite=False,
                    is_mainline=True,
                    head_revision_id=root_revision_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.outfits.add_revision(
                OutfitRevision(
                    id=root_revision_id,
                    session_id=session_id,
                    branch_id=branch_id,
                    base_revision_id=None,
                    parent_revision_id=None,
                    layers_json="[]",
                    created_at=now,
                )
            )
            await uow.commit()
            return await self._session_payload(uow, session)

    async def list_sessions(
        self, *, owner_scope_id: str | None, limit: int = 50
    ) -> dict[str, object]:
        async with self._uow_factory() as uow:
            sessions = await uow.outfits.list_sessions(owner_scope_id, limit=limit + 1)
            has_more = len(sessions) > limit
            items = [await self._session_payload(uow, s) for s in sessions[:limit]]
        return {"items": items, "next_cursor": None, "has_more": has_more}

    async def get_session(
        self, *, session_id: str, owner_scope_id: str | None
    ) -> dict[str, object]:
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def update_session(
        self,
        *,
        session_id: str,
        owner_scope_id: str | None,
        name: str | None,
        favorite: bool | None,
    ) -> dict[str, object]:
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            updated = OutfitSession(
                id=session.id,
                owner_scope_id=session.owner_scope_id,
                name=(name.strip() if name else session.name),
                favorite=session.favorite if favorite is None else favorite,
                person_asset_id=session.person_asset_id,
                layer_definition_version=session.layer_definition_version,
                main_branch_id=session.main_branch_id,
                created_at=session.created_at,
                updated_at=datetime.now(UTC),
            )
            await uow.outfits.update_session(updated)
            await uow.commit()
            return await self._session_payload(uow, updated)

    async def delete_session(
        self, *, session_id: str, owner_scope_id: str | None
    ) -> None:
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            if await uow.outfits.count_unfinished_jobs(session_id=session.id) > 0:
                raise OutfitError(
                    409, "outfit_has_unfinished_jobs", "存在未结束的任务，需先取消或结束后再删除。"
                )
            released: list[str] = []
            for branch in await uow.outfits.list_branches(session.id):
                released.extend(layer.id for layer in await uow.outfits.list_layers(branch.id))
            await uow.asset_references.release_many(
                source_kind="outfit", source_ids=released, at=datetime.now(UTC)
            )
            await uow.outfits.delete_session(session.id)
            await uow.commit()

    async def create_branch(
        self,
        *,
        session_id: str,
        owner_scope_id: str | None,
        name: str | None,
        route: str | None,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branches = await uow.outfits.list_branches(session.id)
            target_route = route or _route_of_main(session, branches) or DEFAULT_ROUTE
            await uow.outfits.add_branch(
                OutfitBranch(
                    id=str(uuid4()),
                    session_id=session.id,
                    name=(name or "分支").strip() or "分支",
                    route=target_route,
                    favorite=False,
                    is_mainline=False,
                    head_revision_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.commit()
            session = await self._require_session(uow, session_id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def update_branch(
        self,
        *,
        session_id: str,
        branch_id: str,
        owner_scope_id: str | None,
        name: str | None,
        favorite: bool | None,
        mainline: bool | None,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branch = await self._require_branch(uow, session.id, branch_id)
            if mainline:
                for other in await uow.outfits.list_branches(session.id):
                    if other.is_mainline and other.id != branch.id:
                        await uow.outfits.update_branch(
                            OutfitBranch(
                                id=other.id,
                                session_id=other.session_id,
                                name=other.name,
                                route=other.route,
                                favorite=other.favorite,
                                is_mainline=False,
                                head_revision_id=other.head_revision_id,
                                created_at=other.created_at,
                                updated_at=now,
                            )
                        )
                session = OutfitSession(
                    id=session.id,
                    owner_scope_id=session.owner_scope_id,
                    name=session.name,
                    favorite=session.favorite,
                    person_asset_id=session.person_asset_id,
                    layer_definition_version=session.layer_definition_version,
                    main_branch_id=branch.id,
                    created_at=session.created_at,
                    updated_at=now,
                )
                await uow.outfits.update_session(session)
            await uow.outfits.update_branch(
                OutfitBranch(
                    id=branch.id,
                    session_id=branch.session_id,
                    name=(name.strip() if name else branch.name),
                    route=branch.route,
                    favorite=branch.favorite if favorite is None else favorite,
                    is_mainline=True if mainline else branch.is_mainline,
                    head_revision_id=branch.head_revision_id,
                    created_at=branch.created_at,
                    updated_at=now,
                )
            )
            await uow.commit()
            session = await self._require_session(uow, session_id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def delete_branch(
        self, *, session_id: str, branch_id: str, owner_scope_id: str | None
    ) -> dict[str, object]:
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branches = await uow.outfits.list_branches(session.id)
            branch = next((b for b in branches if b.id == branch_id), None)
            if branch is None:
                raise OutfitError(404, "outfit_branch_not_found", "穿搭分支不存在。")
            if len(branches) <= 1:
                raise OutfitError(
                    409, "outfit_single_branch", "只有一个分支时请删除整个会话。"
                )
            if branch.is_mainline:
                raise OutfitError(
                    409,
                    "outfit_mainline_locked",
                    "删除当前主线前请先切换主线。",
                )
            branch_layers = await uow.outfits.list_layers(branch.id)
            await uow.asset_references.release_many(
                source_kind="outfit",
                source_ids=[layer.id for layer in branch_layers],
                at=datetime.now(UTC),
            )
            await uow.outfits.delete_branch(branch.id)
            await uow.commit()
            session = await self._require_session(uow, session_id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def add_layer(
        self,
        *,
        session_id: str,
        branch_id: str,
        owner_scope_id: str | None,
        provider_service: ProviderConfigService,
        capacity: Callable[[], bool],
        role: str,
        garment_asset_id: str,
        provider_id: str,
        candidate_count: int,
        mask_asset_id: str | None,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branch = await self._require_branch(uow, session.id, branch_id)
            definitions = await uow.outfits.list_layer_types(session.layer_definition_version)
            definition = next((d for d in definitions if d.role == role), None)
            if definition is None:
                raise OutfitError(422, "invalid_layer_role", "不支持的分层角色。")
            if not await _asset_available(uow, garment_asset_id, "garment", session.owner_scope_id):
                raise OutfitError(422, "invalid_garment_asset", "衣物素材不存在或不可用。")

            config = await provider_service.get(provider_id)
            revision = await provider_service.current_revision(provider_id)
            if config is None or revision is None or config.state not in {"active", "validated"}:
                raise OutfitError(409, "provider_not_usable", "所选 Provider 不可用。")
            capabilities = _as_mapping(json.loads(revision.capabilities_json or "{}"))
            if not _capability_supported(capabilities, "sequential_layering"):
                raise OutfitError(409, "provider_not_usable", "所选 Provider 不支持分层穿搭。")
            roles = _as_mapping(capabilities.get("supported_layer_roles")).get("values")
            if isinstance(roles, list) and roles and role not in roles:
                raise OutfitError(409, "provider_not_usable", "所选 Provider 不支持该层级角色。")
            if mask_asset_id is not None and not _capability_supported(capabilities, "manual_mask"):
                raise OutfitError(409, "provider_not_usable", "所选 Provider 不支持手动遮罩。")
            max_candidates = _as_int(
                _as_mapping(capabilities.get("output_constraints")).get("max_candidates"), 4
            )
            if candidate_count > max_candidates:
                raise OutfitError(409, "provider_not_usable", "所选 Provider 不支持该候选数量。")
            if not capacity():
                raise OutfitError(507, "storage_capacity", "存储空间不足，暂时不能创建任务。")

            try:
                workflow_lock = await lock_active_workflow(
                    uow,
                    adapter_type=revision.adapter_type,
                    vendor_parameters_json=revision.vendor_parameters_json,
                    garment_asset_id=garment_asset_id,
                    mask_asset_id=mask_asset_id,
                    candidate_count=candidate_count,
                )
            except WorkflowLockError as error:
                raise OutfitError(409, error.code, error.detail) from error

            availability = await provider_service.availability_for(config, revision)
            waiting = availability == "temporarily_offline"
            job_id = str(uuid4())
            snapshot = {
                "label": f"{config.display_name} · {revision.model}",
                "adapter_type": revision.adapter_type,
                "model": revision.model,
                "semantic_parameters": json.loads(revision.vendor_parameters_json or "{}"),
                "capabilities_schema_version": 1,
                "capabilities": json.loads(revision.capabilities_json or "{}"),
            }
            job = Job(
                id=job_id,
                owner_scope_id=session.owner_scope_id,
                mode="precise_try_on",
                state="waiting_provider" if waiting else "queued",
                candidate_count=candidate_count,
                garment_asset_id=garment_asset_id,
                provider_id=provider_id,
                provider_revision_id=revision.id,
                provider_snapshot_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
                block_reason="provider_offline" if waiting else None,
                blocked_detail="Provider 暂时离线，恢复后任务会自动继续。" if waiting else None,
                mask_asset_id=mask_asset_id,
                workflow_version_id=workflow_lock[0] if workflow_lock else None,
                workflow_snapshot_json=workflow_lock[1] if workflow_lock else None,
                created_at=now,
                updated_at=now,
            )
            await uow.jobs.add_job(job)
            await uow.jobs.add_person_input(
                JobPersonInput(
                    job_id=job_id,
                    person_asset_id=session.person_asset_id,
                    ordinal=0,
                    created_at=now,
                )
            )
            for candidate_index in range(candidate_count):
                await uow.jobs.add_item(
                    JobItem(
                        id=str(uuid4()),
                        job_id=job_id,
                        person_asset_id=session.person_asset_id,
                        candidate_index=candidate_index,
                        attempt=1,
                        state="waiting_provider" if waiting else "queued",
                        block_reason="provider_offline" if waiting else None,
                        created_at=now,
                        updated_at=now,
                    )
                )
            layer_id = str(uuid4())
            await uow.outfits.add_layer(
                OutfitLayer(
                    id=layer_id,
                    session_id=session.id,
                    branch_id=branch.id,
                    role=role,
                    garment_asset_id=garment_asset_id,
                    layer_order=definition.layer_order,
                    state="pending_reapply",
                    definition_version=session.layer_definition_version,
                    source_layer_id=None,
                    apply_job_id=job_id,
                    selected_output_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            for asset_id in (garment_asset_id, session.person_asset_id):
                await uow.asset_references.add(
                    AssetReference(
                        id=str(uuid4()),
                        asset_id=asset_id,
                        source_kind="outfit",
                        source_id=layer_id,
                        active=True,
                        created_at=now,
                        display_label="分层穿搭",
                    )
                )
            await uow.commit()
            session = await self._require_session(uow, session.id, owner_scope_id)
            return {
                "session": await self._session_payload(uow, session),
                "job": await job_payload(uow, job),
            }

    async def select_revision(
        self,
        *,
        session_id: str,
        branch_id: str,
        revision_id: str,
        owner_scope_id: str | None,
        job_item_id: str,
        output_id: str,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branch = await self._require_branch(uow, session.id, branch_id)
            base = await uow.outfits.get_revision(revision_id)
            if base is None or base.branch_id != branch.id:
                raise OutfitError(404, "outfit_revision_not_found", "穿搭版本不存在。")
            item = await uow.jobs.get_item(job_item_id)
            if item is None:
                raise OutfitError(404, "job_item_not_found", "候选任务不存在。")
            output = await uow.job_outputs.get_output(output_id)
            if output is None or output.job_item_id != job_item_id:
                raise OutfitError(422, "invalid_output", "候选项不属于该任务。")
            layers = await uow.outfits.list_layers(branch.id)
            layer = next(
                (candidate for candidate in layers if candidate.apply_job_id == item.job_id),
                None,
            )
            if layer is None:
                raise OutfitError(404, "outfit_layer_not_found", "层不存在。")
            committed: list[OutfitLayer] = []
            for existing in layers:
                state = existing.state
                selected = existing.selected_output_id
                if existing.id == layer.id:
                    state = "applied"
                    selected = output.id
                elif existing.layer_order > layer.layer_order:
                    state = "pending_reapply"
                committed.append(
                    OutfitLayer(
                        id=existing.id,
                        session_id=existing.session_id,
                        branch_id=existing.branch_id,
                        role=existing.role,
                        garment_asset_id=existing.garment_asset_id,
                        layer_order=existing.layer_order,
                        state=state,
                        definition_version=existing.definition_version,
                        source_layer_id=existing.source_layer_id,
                        apply_job_id=existing.apply_job_id,
                        selected_output_id=selected,
                        created_at=existing.created_at,
                        updated_at=now,
                    )
                )
                await uow.outfits.update_layer(committed[-1])
            new_revision_id = str(uuid4())
            snapshot = [
                _layer_snapshot(layer_item)
                for layer_item in committed
                if layer_item.state == "applied"
            ]
            await uow.outfits.add_revision(
                OutfitRevision(
                    id=new_revision_id,
                    session_id=session.id,
                    branch_id=branch.id,
                    base_revision_id=base.id,
                    parent_revision_id=base.id,
                    layers_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
                    created_at=now,
                )
            )
            await uow.outfits.update_branch(
                OutfitBranch(
                    id=branch.id,
                    session_id=branch.session_id,
                    name=branch.name,
                    route=branch.route,
                    favorite=branch.favorite,
                    is_mainline=branch.is_mainline,
                    head_revision_id=new_revision_id,
                    created_at=branch.created_at,
                    updated_at=now,
                )
            )
            await uow.commit()
            session = await self._require_session(uow, session.id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def remove_layer(
        self,
        *,
        session_id: str,
        branch_id: str,
        layer_id: str,
        owner_scope_id: str | None,
        mode: str,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branch = await self._require_branch(uow, session.id, branch_id)
            layer = await uow.outfits.get_layer(layer_id)
            if layer is None or layer.branch_id != branch.id:
                raise OutfitError(404, "outfit_layer_not_found", "层不存在。")
            layers = await uow.outfits.list_layers(branch.id)
            if mode == "remove":
                await uow.outfits.delete_layer(layer.id)
                await uow.asset_references.release_many(
                    source_kind="outfit", source_ids=[layer.id], at=now
                )
            for existing in layers:
                if existing.id != layer.id and existing.layer_order >= layer.layer_order:
                    await uow.outfits.update_layer(
                        replace(existing, state="pending_reapply", updated_at=now)
                    )
            await uow.commit()
            session = await self._require_session(uow, session.id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def switch_route(
        self, *, session_id: str, owner_scope_id: str | None, route: str
    ) -> dict[str, object]:
        if route not in {"split", "dress"}:
            raise OutfitError(422, "invalid_route", "不支持的穿搭路线。")
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branches = await uow.outfits.list_branches(session.id)
            main = next(
                (b for b in branches if b.id == session.main_branch_id),
                branches[0] if branches else None,
            )
            if main is None:
                raise OutfitError(404, "outfit_branch_not_found", "穿搭分支不存在。")
            main_layers = await uow.outfits.list_layers(main.id)
            definitions = await uow.outfits.list_layer_types(session.layer_definition_version)
            outerwear_order = next(
                (d.layer_order for d in definitions if d.role == "outerwear"), 3
            )
            new_branch_id, root_revision_id = str(uuid4()), str(uuid4())
            await uow.outfits.add_branch(
                OutfitBranch(
                    id=new_branch_id,
                    session_id=session.id,
                    name="连衣裙路线" if route == "dress" else "分体路线",
                    route=route,
                    favorite=False,
                    is_mainline=False,
                    head_revision_id=root_revision_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            await uow.outfits.add_revision(
                OutfitRevision(
                    id=root_revision_id,
                    session_id=session.id,
                    branch_id=new_branch_id,
                    base_revision_id=None,
                    parent_revision_id=None,
                    layers_json="[]",
                    created_at=now,
                )
            )
            for layer in main_layers:
                if layer.role != "outerwear":
                    continue
                new_layer_id = str(uuid4())
                await uow.outfits.add_layer(
                    OutfitLayer(
                        id=new_layer_id,
                        session_id=session.id,
                        branch_id=new_branch_id,
                        role="outerwear",
                        garment_asset_id=layer.garment_asset_id,
                        layer_order=outerwear_order,
                        state="pending_reapply",
                        definition_version=session.layer_definition_version,
                        source_layer_id=layer.id,
                        apply_job_id=None,
                        selected_output_id=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                for asset_id in (layer.garment_asset_id, session.person_asset_id):
                    await uow.asset_references.add(
                        AssetReference(
                            id=str(uuid4()),
                            asset_id=asset_id,
                            source_kind="outfit",
                            source_id=new_layer_id,
                            active=True,
                            created_at=now,
                            display_label="分层穿搭",
                        )
                    )
            await uow.commit()
            session = await self._require_session(uow, session.id, owner_scope_id)
            return await self._session_payload(uow, session)

    async def reapply_layer(
        self,
        *,
        session_id: str,
        branch_id: str,
        layer_id: str,
        owner_scope_id: str | None,
        provider_service: ProviderConfigService,
        capacity: Callable[[], bool],
        provider_id: str | None,
        candidate_count: int,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self._uow_factory() as uow:
            session = await self._require_session(uow, session_id, owner_scope_id)
            branch = await self._require_branch(uow, session.id, branch_id)
            layer = await uow.outfits.get_layer(layer_id)
            if layer is None or layer.branch_id != branch.id:
                raise OutfitError(404, "outfit_layer_not_found", "层不存在。")
            if layer.state != "pending_reapply":
                raise OutfitError(409, "outfit_layer_not_pending", "该层已应用。")
            chosen_provider = provider_id
            if chosen_provider is None:
                original = (
                    await uow.jobs.get_job(layer.apply_job_id)
                    if layer.apply_job_id is not None
                    else None
                )
                if original is None:
                    raise OutfitError(
                        409, "provider_not_usable", "原 Provider 不可用，请显式选择兼容 Provider。"
                    )
                chosen_provider = original.provider_id
            config = await provider_service.get(chosen_provider)
            revision = await provider_service.current_revision(chosen_provider)
            if config is None or revision is None or config.state not in {"active", "validated"}:
                raise OutfitError(
                    409, "provider_not_usable", "没有可用的兼容 Provider，请显式选择。"
                )
            capabilities = _as_mapping(json.loads(revision.capabilities_json or "{}"))
            roles = _as_mapping(capabilities.get("supported_layer_roles")).get("values")
            if not _capability_supported(capabilities, "sequential_layering"):
                raise OutfitError(
                    409, "provider_not_usable", "所选 Provider 不支持分层穿搭。"
                )
            if isinstance(roles, list) and roles and layer.role not in roles:
                raise OutfitError(
                    409, "provider_not_usable", "所选 Provider 不支持该层级角色。"
                )
            if not capacity():
                raise OutfitError(507, "storage_capacity", "存储空间不足，暂时不能创建任务。")
            try:
                workflow_lock = await lock_active_workflow(
                    uow,
                    adapter_type=revision.adapter_type,
                    vendor_parameters_json=revision.vendor_parameters_json,
                    garment_asset_id=layer.garment_asset_id,
                    mask_asset_id=None,
                    candidate_count=candidate_count,
                )
            except WorkflowLockError as error:
                raise OutfitError(409, error.code, error.detail) from error
            availability = await provider_service.availability_for(config, revision)
            waiting = availability == "temporarily_offline"
            job_id = str(uuid4())
            snapshot = {
                "label": f"{config.display_name} · {revision.model}",
                "adapter_type": revision.adapter_type,
                "model": revision.model,
                "semantic_parameters": json.loads(revision.vendor_parameters_json or "{}"),
                "capabilities_schema_version": 1,
                "capabilities": json.loads(revision.capabilities_json or "{}"),
            }
            job = Job(
                id=job_id,
                owner_scope_id=session.owner_scope_id,
                mode="precise_try_on",
                state="waiting_provider" if waiting else "queued",
                candidate_count=candidate_count,
                garment_asset_id=layer.garment_asset_id,
                provider_id=chosen_provider,
                provider_revision_id=revision.id,
                provider_snapshot_json=json.dumps(snapshot, separators=(",", ":"), sort_keys=True),
                block_reason="provider_offline" if waiting else None,
                blocked_detail="Provider 暂时离线，恢复后任务会自动继续。" if waiting else None,
                workflow_version_id=workflow_lock[0] if workflow_lock else None,
                workflow_snapshot_json=workflow_lock[1] if workflow_lock else None,
                created_at=now,
                updated_at=now,
            )
            await uow.jobs.add_job(job)
            await uow.jobs.add_person_input(
                JobPersonInput(
                    job_id=job_id,
                    person_asset_id=session.person_asset_id,
                    ordinal=0,
                    created_at=now,
                )
            )
            for candidate_index in range(candidate_count):
                await uow.jobs.add_item(
                    JobItem(
                        id=str(uuid4()),
                        job_id=job_id,
                        person_asset_id=session.person_asset_id,
                        candidate_index=candidate_index,
                        attempt=1,
                        state="waiting_provider" if waiting else "queued",
                        block_reason="provider_offline" if waiting else None,
                        created_at=now,
                        updated_at=now,
                    )
                )
            await uow.outfits.update_layer(replace(layer, apply_job_id=job_id, updated_at=now))
            await uow.commit()
            session = await self._require_session(uow, session.id, owner_scope_id)
            return {
                "session": await self._session_payload(uow, session),
                "job": await job_payload(uow, job),
            }

    # -- helpers ---------------------------------------------------------

    async def _require_session(
        self, uow: SqlAlchemyUnitOfWork, session_id: str, owner_scope_id: str | None
    ) -> OutfitSession:
        session = await uow.outfits.get_session(session_id, owner_scope_id)
        if session is None:
            raise OutfitError(404, "outfit_session_not_found", "穿搭会话不存在。")
        return session

    async def _require_branch(
        self, uow: SqlAlchemyUnitOfWork, session_id: str, branch_id: str
    ) -> OutfitBranch:
        branch = await uow.outfits.get_branch(branch_id)
        if branch is None or branch.session_id != session_id:
            raise OutfitError(404, "outfit_branch_not_found", "穿搭分支不存在。")
        return branch

    async def _session_payload(
        self, uow: SqlAlchemyUnitOfWork, session: OutfitSession
    ) -> dict[str, object]:
        branches = await uow.outfits.list_branches(session.id)
        layer_types = await uow.outfits.list_layer_types(session.layer_definition_version)
        branch_payloads: list[dict[str, object]] = []
        head_revision: dict[str, object] | None = None
        for branch in branches:
            revisions = await uow.outfits.list_revisions(branch.id)
            working_layers = await uow.outfits.list_layers(branch.id)
            branch_payloads.append(
                {
                    "id": branch.id,
                    "name": branch.name,
                    "route": branch.route,
                    "is_mainline": branch.is_mainline,
                    "favorite": branch.favorite,
                    "head_revision_id": branch.head_revision_id,
                    "revision_count": len(revisions),
                    "unfinished_job_count": 0,
                    "layers": [_layer_payload(layer) for layer in working_layers],
                    "created_at": branch.created_at,
                    "updated_at": branch.updated_at,
                }
            )
            if branch.head_revision_id is not None and head_revision is None:
                revision = await uow.outfits.get_revision(branch.head_revision_id)
                if revision is not None:
                    head_revision = _revision_payload(revision)
        return {
            "id": session.id,
            "name": session.name,
            "favorite": session.favorite,
            "person_asset_id": session.person_asset_id,
            "layer_definition_version": session.layer_definition_version,
            "layer_types": [
                _layer_type_payload(definition) for definition in layer_types
            ],
            "main_branch_id": session.main_branch_id,
            "head_revision": head_revision,
            "branches": branch_payloads,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }


def _route_of_main(session: OutfitSession, branches: list[OutfitBranch]) -> str | None:
    for branch in branches:
        if branch.id == session.main_branch_id:
            return branch.route
    return None


def _parsed(raw: str) -> list[object]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return cast("list[object]", value)


def _as_mapping(value: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _as_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _capability_supported(capabilities: Mapping[str, object], name: str) -> bool:
    return _as_mapping(capabilities.get(name)).get("supported") is True


async def _asset_available(
    uow: SqlAlchemyUnitOfWork, asset_id: str, kind: str, owner_scope_id: str | None
) -> bool:
    return await uow.outfits.asset_available(asset_id, kind, owner_scope_id)


def _layer_payload(layer: OutfitLayer) -> dict[str, object]:
    return {
        "id": layer.id,
        "role": layer.role,
        "garment_asset_id": layer.garment_asset_id,
        "order": layer.layer_order,
        "state": layer.state,
        "definition_version": layer.definition_version,
        "source_layer_id": layer.source_layer_id,
        "apply_job_id": layer.apply_job_id,
        "selected_output_id": layer.selected_output_id,
        "created_at": layer.created_at,
        "updated_at": layer.updated_at,
    }


def _layer_snapshot(layer: OutfitLayer) -> dict[str, object]:
    return {
        "id": layer.id,
        "role": layer.role,
        "garment_asset_id": layer.garment_asset_id,
        "order": layer.layer_order,
        "state": layer.state,
        "selected_output_id": layer.selected_output_id,
    }


def _layer_type_payload(definition: LayerTypeDefinition) -> dict[str, object]:
    return {
        "key": definition.role,
        "body_region": definition.body_region,
        "order": definition.layer_order,
        "compatible_roles": _parsed(definition.compatible_roles_json),
        "conflicting_roles": _parsed(definition.conflicting_roles_json),
        "required_capabilities": _parsed(definition.required_capabilities_json),
    }


def _revision_payload(revision: Any) -> dict[str, object]:
    return {
        "id": revision.id,
        "branch_id": revision.branch_id,
        "base_revision_id": revision.base_revision_id,
        "parent_revision_id": revision.parent_revision_id,
        "layers": _parsed(revision.layers_json),
        "created_at": revision.created_at,
    }
