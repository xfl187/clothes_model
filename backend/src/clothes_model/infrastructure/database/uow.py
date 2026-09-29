"""SQLAlchemy implementation of the Unit of Work port."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clothes_model.core.persistence import UnitOfWork
from clothes_model.infrastructure.database.repositories import (
    SqlAlchemyAccessTokenRepository,
    SqlAlchemyAdminSessionRepository,
    SqlAlchemyAssetReferenceRepository,
    SqlAlchemyAssetRepository,
    SqlAlchemyAuthThrottleRepository,
    SqlAlchemyComfyNodeRepository,
    SqlAlchemyGeneratedOutputRepository,
    SqlAlchemyIdempotencyRepository,
    SqlAlchemyJobExecutionEventRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyOwnerScopeRepository,
    SqlAlchemyProviderConfigRepository,
    SqlAlchemySecurityAuditRepository,
    SqlAlchemyServerIdentityRepository,
    SqlAlchemyStoredObjectRepository,
    SqlAlchemyUploadRepository,
    SqlAlchemyWorkflowRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return self._session

    @property
    def access_tokens(self) -> SqlAlchemyAccessTokenRepository:
        return SqlAlchemyAccessTokenRepository(self.session)

    @property
    def admin_sessions(self) -> SqlAlchemyAdminSessionRepository:
        return SqlAlchemyAdminSessionRepository(self.session)

    @property
    def auth_throttles(self) -> SqlAlchemyAuthThrottleRepository:
        return SqlAlchemyAuthThrottleRepository(self.session)

    @property
    def idempotency(self) -> SqlAlchemyIdempotencyRepository:
        return SqlAlchemyIdempotencyRepository(self.session)

    @property
    def stored_objects(self) -> SqlAlchemyStoredObjectRepository:
        return SqlAlchemyStoredObjectRepository(self.session)

    @property
    def uploads(self) -> SqlAlchemyUploadRepository:
        return SqlAlchemyUploadRepository(self.session)

    @property
    def assets(self) -> SqlAlchemyAssetRepository:
        return SqlAlchemyAssetRepository(self.session)

    @property
    def asset_references(self) -> SqlAlchemyAssetReferenceRepository:
        return SqlAlchemyAssetReferenceRepository(self.session)

    @property
    def security_audit(self) -> SqlAlchemySecurityAuditRepository:
        return SqlAlchemySecurityAuditRepository(self.session)

    @property
    def owner_scopes(self) -> SqlAlchemyOwnerScopeRepository:
        return SqlAlchemyOwnerScopeRepository(self.session)

    @property
    def server_identity(self) -> SqlAlchemyServerIdentityRepository:
        return SqlAlchemyServerIdentityRepository(self.session)

    @property
    def provider_configs(self) -> SqlAlchemyProviderConfigRepository:
        return SqlAlchemyProviderConfigRepository(self.session)

    @property
    def comfy_node(self) -> SqlAlchemyComfyNodeRepository:
        return SqlAlchemyComfyNodeRepository(self.session)

    @property
    def workflows(self) -> SqlAlchemyWorkflowRepository:
        return SqlAlchemyWorkflowRepository(self.session)

    @property
    def jobs(self) -> SqlAlchemyJobRepository:
        return SqlAlchemyJobRepository(self.session)

    @property
    def job_outputs(self) -> SqlAlchemyGeneratedOutputRepository:
        return SqlAlchemyGeneratedOutputRepository(self.session)

    @property
    def job_events(self) -> SqlAlchemyJobExecutionEventRepository:
        return SqlAlchemyJobExecutionEventRepository(self.session)

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if self._session.in_transaction():
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
