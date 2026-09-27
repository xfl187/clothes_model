"""Async SQLAlchemy adapters for Phase 2 persistence ports."""

from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import RowMapping
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
        values = {
            "id": asset.id,
            "kind": asset.kind,
            "stored_object_id": asset.stored_object_id,
            "favorite": asset.favorite,
            "content_state": asset.content_state,
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


def _access_token(row: RowMapping) -> AccessToken:
    return AccessToken(**dict(row))


def _admin_session(row: RowMapping) -> AdminSession:
    return AdminSession(**dict(row))
