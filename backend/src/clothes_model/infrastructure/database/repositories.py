"""Async SQLAlchemy adapters for Phase 2 persistence ports."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.engine import CursorResult, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from clothes_model.core.persistence import PersistenceConflict
from clothes_model.infrastructure.database import models
from clothes_model.modules.assets.domain import (
    Asset,
    AssetReference,
    GarmentMetadata,
    IdempotencyRecord,
    PersonMetadata,
    StoredObject,
    UploadSession,
)
from clothes_model.modules.auth.domain import (
    AccessToken,
    AdminSession,
    AuthThrottle,
    SecurityAuditEvent,
)
from clothes_model.modules.comfy.domain import ComfyNodeConfig
from clothes_model.modules.jobs.domain import (
    GeneratedOutputRecord,
    Job,
    JobExecutionEvent,
    JobItem,
    JobPersonInput,
)
from clothes_model.modules.providers.domain import (
    ProviderConfig,
    ProviderConfigRevision,
    ProviderDefaultSelection,
)
from clothes_model.modules.workflows.domain import WorkflowValidationRun, WorkflowVersion


async def _insert(session: AsyncSession, table: Any, values: Mapping[str, object]) -> None:
    try:
        await session.execute(insert(table).values(**values))
    except IntegrityError as error:
        raise PersistenceConflict(f"constraint conflict in {table.name}") from error


async def _one_mapping(session: AsyncSession, statement: Any) -> RowMapping | None:
    result = await session.execute(statement)
    row = result.mappings().one_or_none()
    return None if row is None else row


class SqlAlchemyAccessTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: AccessToken) -> None:
        await _insert(self._session, models.access_tokens, asdict(token))

    async def get(self, token_id: str) -> AccessToken | None:
        row = await _one_mapping(
            self._session,
            select(models.access_tokens).where(models.access_tokens.c.id == token_id),
        )
        return None if row is None else _access_token(row)

    async def get_by_public_id(self, public_id: str) -> AccessToken | None:
        row = await _one_mapping(
            self._session,
            select(models.access_tokens).where(models.access_tokens.c.public_id == public_id),
        )
        return None if row is None else _access_token(row)

    async def list_active(self, scope: str) -> list[AccessToken]:
        result = await self._session.execute(
            select(models.access_tokens)
            .where(
                models.access_tokens.c.scope == scope,
                models.access_tokens.c.status == "active",
            )
            .order_by(models.access_tokens.c.created_at, models.access_tokens.c.id)
        )
        return [_access_token(row) for row in result.mappings().all()]

    async def replace(self, token: AccessToken) -> None:
        await self._session.execute(
            update(models.access_tokens)
            .where(models.access_tokens.c.id == token.id)
            .values(**asdict(token))
        )


class SqlAlchemyAdminSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: AdminSession) -> None:
        await _insert(self._session, models.admin_sessions, asdict(session))

    async def get(self, session_id: str) -> AdminSession | None:
        row = await _one_mapping(
            self._session,
            select(models.admin_sessions).where(models.admin_sessions.c.id == session_id),
        )
        return None if row is None else _admin_session(row)

    async def get_by_digest(self, digest: str) -> AdminSession | None:
        row = await _one_mapping(
            self._session,
            select(models.admin_sessions).where(models.admin_sessions.c.session_digest == digest),
        )
        return None if row is None else _admin_session(row)

    async def revoke_for_token(self, token_id: str, revoked_at: datetime) -> None:
        await self._session.execute(
            update(models.admin_sessions)
            .where(
                models.admin_sessions.c.token_id == token_id,
                models.admin_sessions.c.state == "active",
            )
            .values(state="revoked", revoked_at=revoked_at)
        )

    async def replace(self, session: AdminSession) -> None:
        await self._session.execute(
            update(models.admin_sessions)
            .where(models.admin_sessions.c.id == session.id)
            .values(**asdict(session))
        )


class SqlAlchemyAuthThrottleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, throttle: AuthThrottle) -> None:
        await _insert(self._session, models.auth_throttle_state, asdict(throttle))

    async def get_by_key(self, throttle_key: str) -> AuthThrottle | None:
        row = await _one_mapping(
            self._session,
            select(models.auth_throttle_state).where(
                models.auth_throttle_state.c.throttle_key == throttle_key
            ),
        )
        return None if row is None else AuthThrottle(**dict(row))

    async def replace(self, throttle: AuthThrottle) -> None:
        await self._session.execute(
            update(models.auth_throttle_state)
            .where(models.auth_throttle_state.c.id == throttle.id)
            .values(**asdict(throttle))
        )


class SqlAlchemyIdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: IdempotencyRecord) -> None:
        await _insert(self._session, models.idempotency_records, asdict(record))

    async def get_bound(
        self, actor_scope: str, actor_id: str, operation: str, key_digest: str
    ) -> IdempotencyRecord | None:
        table = models.idempotency_records
        row = await _one_mapping(
            self._session,
            select(table).where(
                table.c.actor_scope == actor_scope,
                table.c.actor_id == actor_id,
                table.c.operation == operation,
                table.c.key_digest == key_digest,
            ),
        )
        return None if row is None else IdempotencyRecord(**dict(row))


class SqlAlchemyStoredObjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, stored_object: StoredObject) -> None:
        await _insert(self._session, models.stored_objects, asdict(stored_object))

    async def get(self, object_id: str) -> StoredObject | None:
        row = await _one_mapping(
            self._session,
            select(models.stored_objects).where(models.stored_objects.c.id == object_id),
        )
        return None if row is None else StoredObject(**dict(row))

    async def get_by_hash(self, sha256: str) -> StoredObject | None:
        row = await _one_mapping(
            self._session,
            select(models.stored_objects).where(models.stored_objects.c.sha256 == sha256),
        )
        return None if row is None else StoredObject(**dict(row))


class SqlAlchemyUploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, upload: UploadSession) -> None:
        values = asdict(upload)
        values["updated_at"] = upload.updated_at or upload.created_at
        await _insert(self._session, models.upload_sessions, values)

    async def get(self, upload_id: str) -> UploadSession | None:
        row = await _one_mapping(
            self._session,
            select(models.upload_sessions).where(models.upload_sessions.c.id == upload_id),
        )
        return None if row is None else UploadSession(**dict(row))


class SqlAlchemyAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, asset: Asset) -> None:
        owner_scope_id = asset.owner_scope_id
        if owner_scope_id is None:
            owner_scope_id = await self._session.scalar(select(models.owner_scopes.c.id).limit(1))
        values = {
            "id": asset.id,
            "kind": asset.kind,
            "owner_scope_id": owner_scope_id,
            "stored_object_id": asset.stored_object_id,
            "favorite": asset.favorite,
            "content_state": asset.content_state,
            "durable_client_copy_confirmed": asset.durable_client_copy_confirmed,
            "client_asset_id": asset.client_asset_id,
            "cleanup_after": asset.cleanup_after,
            "created_at": asset.created_at,
            "updated_at": asset.updated_at,
            "deleted_at": asset.deleted_at,
        }
        try:
            await self._session.execute(insert(models.assets).values(**values))
            if asset.kind == "person" and asset.person is not None and asset.garment is None:
                await self._session.execute(insert(models.person_assets).values(asset_id=asset.id))
            elif asset.kind == "garment" and asset.garment is not None and asset.person is None:
                await self._session.execute(
                    insert(models.garment_assets).values(
                        asset_id=asset.id,
                        category=asset.garment.category,
                        source=asset.garment.source,
                    )
                )
            elif (
                asset.kind in {"generated_output", "mask"}
                and asset.person is None
                and asset.garment is None
            ):
                pass
            else:
                raise PersistenceConflict("asset must have exactly one matching subtype")
        except IntegrityError as error:
            raise PersistenceConflict("constraint conflict in assets") from error

    async def get(self, asset_id: str) -> Asset | None:
        row = await _one_mapping(
            self._session,
            select(models.assets).where(models.assets.c.id == asset_id),
        )
        if row is None:
            return None
        person_row = await _one_mapping(
            self._session,
            select(models.person_assets).where(models.person_assets.c.asset_id == asset_id),
        )
        garment_row = await _one_mapping(
            self._session,
            select(models.garment_assets).where(models.garment_assets.c.asset_id == asset_id),
        )
        return Asset(
            **dict(row),
            person=None if person_row is None else PersonMetadata(asset_id=asset_id),
            garment=None if garment_row is None else GarmentMetadata(**dict(garment_row)),
        )


class SqlAlchemyAssetReferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, reference: AssetReference) -> None:
        await _insert(self._session, models.asset_references, asdict(reference))

    async def list_active(self, asset_id: str) -> list[AssetReference]:
        result = await self._session.execute(
            select(models.asset_references)
            .where(
                models.asset_references.c.asset_id == asset_id,
                models.asset_references.c.active.is_(True),
            )
            .order_by(models.asset_references.c.created_at, models.asset_references.c.id)
        )
        return [AssetReference(**dict(row)) for row in result.mappings().all()]


class SqlAlchemySecurityAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: SecurityAuditEvent) -> None:
        await _insert(self._session, models.security_audit_events, asdict(event))


class SqlAlchemyOwnerScopeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, default_id: str, created_at: datetime) -> str:
        existing = await self._session.scalar(select(models.owner_scopes.c.id).limit(1))
        if existing is not None:
            return str(existing)
        await self._session.execute(
            insert(models.owner_scopes).values(id=default_id, created_at=created_at)
        )
        return default_id


class SqlAlchemyServerIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, default_id: str, created_at: datetime) -> str:
        existing = await self._session.scalar(select(models.server_identity.c.id).limit(1))
        if existing is not None:
            return str(existing)
        await self._session.execute(
            insert(models.server_identity).values(id=default_id, created_at=created_at)
        )
        return default_id


class SqlAlchemyProviderConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_config(self, config: ProviderConfig) -> None:
        await _insert(self._session, models.provider_configs, asdict(config))

    async def get_config(self, provider_id: str) -> ProviderConfig | None:
        row = await _one_mapping(
            self._session,
            select(models.provider_configs).where(models.provider_configs.c.id == provider_id),
        )
        return None if row is None else ProviderConfig(**dict(row))

    async def list_configs(self) -> list[ProviderConfig]:
        result = await self._session.execute(
            select(models.provider_configs).order_by(
                models.provider_configs.c.created_at, models.provider_configs.c.id
            )
        )
        return [ProviderConfig(**dict(row)) for row in result.mappings().all()]

    async def update_config(self, config: ProviderConfig) -> None:
        await self._session.execute(
            update(models.provider_configs)
            .where(models.provider_configs.c.id == config.id)
            .values(**asdict(config))
        )

    async def has_references(self, provider_id: str) -> bool:
        job_id = await self._session.scalar(
            select(models.jobs.c.id).where(models.jobs.c.provider_id == provider_id).limit(1)
        )
        return job_id is not None

    async def delete_config(self, provider_id: str) -> None:
        await self._session.execute(
            delete(models.provider_configs).where(models.provider_configs.c.id == provider_id)
        )

    async def add_revision(self, revision: ProviderConfigRevision) -> None:
        await _insert(self._session, models.provider_config_revisions, asdict(revision))

    async def get_revision(self, revision_id: str) -> ProviderConfigRevision | None:
        row = await _one_mapping(
            self._session,
            select(models.provider_config_revisions).where(
                models.provider_config_revisions.c.id == revision_id
            ),
        )
        return None if row is None else ProviderConfigRevision(**dict(row))

    async def list_revisions(self, provider_id: str) -> list[ProviderConfigRevision]:
        result = await self._session.execute(
            select(models.provider_config_revisions)
            .where(models.provider_config_revisions.c.provider_id == provider_id)
            .order_by(models.provider_config_revisions.c.revision)
        )
        return [ProviderConfigRevision(**dict(row)) for row in result.mappings().all()]

    async def get_current_revision(self, provider_id: str) -> ProviderConfigRevision | None:
        row = await _one_mapping(
            self._session,
            select(models.provider_config_revisions)
            .where(models.provider_config_revisions.c.provider_id == provider_id)
            .order_by(models.provider_config_revisions.c.revision.desc())
            .limit(1),
        )
        return None if row is None else ProviderConfigRevision(**dict(row))

    async def set_default(self, selection: ProviderDefaultSelection) -> None:
        await self._session.execute(delete(models.provider_default_selection))
        await _insert(self._session, models.provider_default_selection, asdict(selection))

    async def get_default(self) -> ProviderDefaultSelection | None:
        row = await _one_mapping(
            self._session,
            select(models.provider_default_selection).where(
                models.provider_default_selection.c.id == "default"
            ),
        )
        return None if row is None else ProviderDefaultSelection(**dict(row))

    async def clear_default(self) -> None:
        await self._session.execute(delete(models.provider_default_selection))


class SqlAlchemyComfyNodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> ComfyNodeConfig | None:
        row = await _one_mapping(
            self._session,
            select(models.comfy_node_config).where(models.comfy_node_config.c.id == "default"),
        )
        return None if row is None else ComfyNodeConfig(**dict(row))

    async def save(self, config: ComfyNodeConfig) -> None:
        if config.id != "default":
            raise PersistenceConflict("Comfy node configuration must use the singleton id")
        existing = await self.get()
        if existing is None:
            await _insert(self._session, models.comfy_node_config, asdict(config))
            return
        await self._session.execute(
            update(models.comfy_node_config)
            .where(models.comfy_node_config.c.id == "default")
            .values(**asdict(config))
        )


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, workflow: WorkflowVersion) -> None:
        await _insert(self._session, models.workflow_versions, asdict(workflow))

    async def get(self, workflow_version_id: str) -> WorkflowVersion | None:
        row = await _one_mapping(
            self._session,
            select(models.workflow_versions).where(
                models.workflow_versions.c.id == workflow_version_id
            ),
        )
        return None if row is None else WorkflowVersion(**dict(row))

    async def get_by_identity(self, workflow_id: str, version: int) -> WorkflowVersion | None:
        row = await _one_mapping(
            self._session,
            select(models.workflow_versions).where(
                models.workflow_versions.c.workflow_id == workflow_id,
                models.workflow_versions.c.version == version,
            ),
        )
        return None if row is None else WorkflowVersion(**dict(row))

    async def list_all(self, limit: int = 100) -> list[WorkflowVersion]:
        result = await self._session.execute(
            select(models.workflow_versions)
            .order_by(models.workflow_versions.c.created_at.desc())
            .limit(limit)
        )
        return [WorkflowVersion(**dict(row)) for row in result.mappings().all()]

    async def list_versions(self, workflow_id: str) -> list[WorkflowVersion]:
        result = await self._session.execute(
            select(models.workflow_versions)
            .where(models.workflow_versions.c.workflow_id == workflow_id)
            .order_by(models.workflow_versions.c.version)
        )
        return [WorkflowVersion(**dict(row)) for row in result.mappings().all()]

    async def get_active(self, mode: str) -> WorkflowVersion | None:
        row = await _one_mapping(
            self._session,
            select(models.workflow_versions).where(
                models.workflow_versions.c.mode == mode,
                models.workflow_versions.c.state == "active",
            ),
        )
        return None if row is None else WorkflowVersion(**dict(row))

    async def update_lifecycle(self, workflow: WorkflowVersion) -> None:
        await self._session.execute(
            update(models.workflow_versions)
            .where(models.workflow_versions.c.id == workflow.id)
            .values(
                state=workflow.state,
                validation_json=workflow.validation_json,
                validated_at=workflow.validated_at,
                activated_at=workflow.activated_at,
                retired_at=workflow.retired_at,
            )
        )

    async def add_validation(self, run: WorkflowValidationRun) -> None:
        await _insert(self._session, models.workflow_validation_runs, asdict(run))


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_job(self, job: Job) -> None:
        values = asdict(job)
        if values["owner_scope_id"] is None:
            values["owner_scope_id"] = await self._session.scalar(
                select(models.assets.c.owner_scope_id).where(
                    models.assets.c.id == job.garment_asset_id
                )
            )
        await _insert(self._session, models.jobs, values)

    async def get_job(self, job_id: str, owner_scope_id: str | None = None) -> Job | None:
        statement = select(models.jobs).where(models.jobs.c.id == job_id)
        if owner_scope_id is not None:
            statement = statement.where(models.jobs.c.owner_scope_id == owner_scope_id)
        row = await _one_mapping(
            self._session,
            statement,
        )
        return None if row is None else Job(**dict(row))

    async def list_jobs(
        self, *, state: str | None = None, limit: int = 50,
        owner_scope_id: str | None = None,
    ) -> list[Job]:
        statement = select(models.jobs)
        if owner_scope_id is not None:
            statement = statement.where(models.jobs.c.owner_scope_id == owner_scope_id)
        if state is not None:
            statement = statement.where(models.jobs.c.state == state)
        statement = statement.order_by(
            models.jobs.c.created_at.desc(), models.jobs.c.id.desc()
        ).limit(limit)
        result = await self._session.execute(statement)
        return [Job(**dict(row)) for row in result.mappings().all()]

    async def update_job(self, job: Job) -> None:
        await self._session.execute(
            update(models.jobs).where(models.jobs.c.id == job.id).values(**asdict(job))
        )

    async def compare_and_set_job_state(
        self,
        job_id: str,
        expected_states: Collection[str],
        state: str,
        values: Mapping[str, object] | None = None,
    ) -> bool:
        payload: dict[str, object] = dict(values or {})
        payload["state"] = state
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(models.jobs)
                .where(
                    models.jobs.c.id == job_id,
                    models.jobs.c.state.in_(list(expected_states)),
                )
                .values(**payload)
            ),
        )
        return result.rowcount == 1

    async def add_person_input(self, person_input: JobPersonInput) -> None:
        await _insert(self._session, models.job_person_inputs, asdict(person_input))

    async def list_person_inputs(self, job_id: str) -> list[JobPersonInput]:
        result = await self._session.execute(
            select(models.job_person_inputs)
            .where(models.job_person_inputs.c.job_id == job_id)
            .order_by(models.job_person_inputs.c.ordinal)
        )
        return [JobPersonInput(**dict(row)) for row in result.mappings().all()]

    async def add_item(self, item: JobItem) -> None:
        await _insert(self._session, models.job_items, asdict(item))

    async def get_item(self, item_id: str) -> JobItem | None:
        row = await _one_mapping(
            self._session,
            select(models.job_items).where(models.job_items.c.id == item_id),
        )
        return None if row is None else JobItem(**dict(row))

    async def list_items(self, job_id: str) -> list[JobItem]:
        result = await self._session.execute(
            select(models.job_items)
            .where(models.job_items.c.job_id == job_id)
            .order_by(
                models.job_items.c.candidate_index,
                models.job_items.c.attempt,
                models.job_items.c.id,
            )
        )
        return [JobItem(**dict(row)) for row in result.mappings().all()]

    async def update_item(self, item: JobItem) -> None:
        await self._session.execute(
            update(models.job_items).where(models.job_items.c.id == item.id).values(**asdict(item))
        )

    async def compare_and_set_item_state(
        self,
        item_id: str,
        expected_states: Collection[str],
        state: str,
        values: Mapping[str, object] | None = None,
    ) -> bool:
        payload: dict[str, object] = dict(values or {})
        payload["state"] = state
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(models.job_items)
                .where(
                    models.job_items.c.id == item_id,
                    models.job_items.c.state.in_(list(expected_states)),
                )
                .values(**payload)
            ),
        )
        return result.rowcount == 1

    async def list_claimable_item_ids(
        self, *, now: datetime, states: Collection[str], limit: int = 1
    ) -> list[str]:
        statement = (
            select(models.job_items.c.id)
            .where(
                models.job_items.c.state.in_(list(states)),
                or_(
                    models.job_items.c.next_attempt_at.is_(None),
                    models.job_items.c.next_attempt_at <= now,
                ),
                or_(
                    models.job_items.c.claimant_token.is_(None),
                    models.job_items.c.lease_expires_at < now,
                ),
            )
            .order_by(models.job_items.c.created_at, models.job_items.c.id)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [str(row[0]) for row in result.all()]

    async def list_external_reconciliation_candidates(self, *, limit: int = 20) -> list[JobItem]:
        result = await self._session.execute(
            select(models.job_items)
            .where(
                models.job_items.c.external_execution_id.is_not(None),
                models.job_items.c.state.in_(["needs_attention", "waiting_provider", "running"]),
            )
            .order_by(models.job_items.c.updated_at, models.job_items.c.id)
            .limit(limit)
        )
        return [JobItem(**dict(row)) for row in result.mappings().all()]

    async def claim_item(
        self,
        item_id: str,
        *,
        claimant_token: str,
        claimed_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(models.job_items)
                .where(
                    models.job_items.c.id == item_id,
                    or_(
                        models.job_items.c.claimant_token.is_(None),
                        models.job_items.c.lease_expires_at < claimed_at,
                    ),
                )
                .values(
                    claimant_token=claimant_token,
                    claimed_at=claimed_at,
                    lease_expires_at=lease_expires_at,
                )
            ),
        )
        return result.rowcount == 1

    async def release_claim(self, item_id: str) -> bool:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(models.job_items)
                .where(models.job_items.c.id == item_id)
                .values(claimant_token=None, claimed_at=None, lease_expires_at=None)
            ),
        )
        return result.rowcount == 1

    async def list_claimed_item_ids(self, *, claimant_token: str) -> Sequence[str]:
        result = await self._session.execute(
            select(models.job_items.c.id)
            .where(models.job_items.c.claimant_token == claimant_token)
            .order_by(models.job_items.c.created_at, models.job_items.c.id)
        )
        return [str(row[0]) for row in result.all()]


class SqlAlchemyGeneratedOutputRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_output(self, output: GeneratedOutputRecord) -> None:
        await _insert(self._session, models.generated_outputs, asdict(output))

    async def get_output(self, output_id: str) -> GeneratedOutputRecord | None:
        row = await _one_mapping(
            self._session,
            select(models.generated_outputs).where(models.generated_outputs.c.id == output_id),
        )
        return None if row is None else GeneratedOutputRecord(**dict(row))

    async def list_outputs(self, job_item_id: str) -> list[GeneratedOutputRecord]:
        result = await self._session.execute(
            select(models.generated_outputs)
            .where(models.generated_outputs.c.job_item_id == job_item_id)
            .order_by(models.generated_outputs.c.created_at, models.generated_outputs.c.id)
        )
        return [GeneratedOutputRecord(**dict(row)) for row in result.mappings().all()]


class SqlAlchemyJobExecutionEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_event(self, event: JobExecutionEvent) -> None:
        await _insert(self._session, models.job_execution_events, asdict(event))

    async def list_events(self, job_id: str) -> list[JobExecutionEvent]:
        result = await self._session.execute(
            select(models.job_execution_events)
            .where(models.job_execution_events.c.job_id == job_id)
            .order_by(
                models.job_execution_events.c.occurred_at,
                models.job_execution_events.c.id,
            )
        )
        return [JobExecutionEvent(**dict(row)) for row in result.mappings().all()]


def _access_token(row: RowMapping) -> AccessToken:
    return AccessToken(**dict(row))


def _admin_session(row: RowMapping) -> AdminSession:
    return AdminSession(**dict(row))
