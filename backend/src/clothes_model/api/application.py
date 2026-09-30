"""FastAPI application factory and lifecycle."""

import asyncio
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clothes_model import __version__
from clothes_model.api.middleware import RequestContextMiddleware
from clothes_model.api.routes import register_routes
from clothes_model.api.static_web import SpaStaticFiles
from clothes_model.core.config import Settings, get_settings
from clothes_model.core.logging import configure_logging, get_logger
from clothes_model.core.problems import register_problem_handlers
from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.scheduler import JobScheduler, SchedulerCoordinator
from clothes_model.infrastructure.security import (
    AesGcmSecretCipher,
    load_master_key,
)
from clothes_model.infrastructure.storage import (
    LocalFileStorage,
    WorkflowArtifactStorage,
    reconcile_upload_sessions,
)
from clothes_model.modules.cleanup.service import run_local_first_cleanup
from clothes_model.modules.jobs.infrastructure.execution import JobExecutionService
from clothes_model.modules.providers.application.ports import ProviderAdapter
from clothes_model.modules.providers.application.services import ProviderConfigService
from clothes_model.modules.providers.infrastructure import (
    ComfyUIAdapter,
    FakeImageEditAdapter,
    ProviderRegistry,
    VolcengineArkSeedreamAdapter,
)


def _load_secret_cipher(settings: Settings) -> AesGcmSecretCipher | None:
    if settings.encryption_master_key_file is None:
        return None
    # A configured-but-invalid key is a deployment error, not an optional
    # credential boundary. Failing startup here prevents a healthy-looking
    # instance from rejecting Provider saves later with secret_key_unavailable.
    return AesGcmSecretCipher(load_master_key(settings.encryption_master_key_file))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application instance for runtime and tests."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    logger = get_logger(__name__)
    database = create_database_runtime(
        resolved_settings.database_url,
        resolved_settings.sqlite_busy_timeout_ms,
    )
    storage = LocalFileStorage(resolved_settings.storage_root)
    workflow_artifacts = WorkflowArtifactStorage(resolved_settings.storage_root)
    secret_cipher = _load_secret_cipher(resolved_settings)
    ark_adapter = VolcengineArkSeedreamAdapter()
    comfy_http_client = httpx2.AsyncClient(trust_env=False, follow_redirects=False)

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(database.sessions)

    comfy_adapter = ComfyUIAdapter(
        uow_factory, workflow_artifacts, secret_cipher, client=comfy_http_client
    )
    adapters: list[ProviderAdapter] = [ark_adapter, comfy_adapter]
    if resolved_settings.environment != "production":
        adapters.append(FakeImageEditAdapter())
    provider_registry = ProviderRegistry(adapters, environment=resolved_settings.environment)

    provider_service = ProviderConfigService(uow_factory, provider_registry, secret_cipher)

    def capacity_available() -> bool:
        usage = shutil.disk_usage(storage.root)
        return usage.free - resolved_settings.storage_reserve_bytes > 0

    job_execution = JobExecutionService(
        uow_factory,
        provider_service,
        provider_registry,
        storage,
        capacity=capacity_available,
    )
    scheduler = SchedulerCoordinator(
        enabled=resolved_settings.scheduler_enabled,
        lock_path=resolved_settings.instance_lock_path,
        scheduler=JobScheduler(
            database.sessions,
            job_execution,
            poll_interval_seconds=resolved_settings.scheduler_poll_interval_seconds,
            batch_size=resolved_settings.scheduler_batch_size,
            lease_minutes=resolved_settings.scheduler_lease_minutes,
            capacity=capacity_available,
        ),
    )

    async def maintain_uploads() -> None:
        while True:
            await asyncio.sleep(resolved_settings.upload_maintenance_interval_seconds)
            try:
                await reconcile_upload_sessions(database.sessions, storage)
            except Exception:
                logger.exception("upload_maintenance_failed")

    async def maintain_local_first_assets() -> None:
        while True:
            await asyncio.sleep(resolved_settings.local_first_cleanup_interval_seconds)
            try:
                await run_local_first_cleanup(database.sessions, storage)
            except Exception:
                logger.exception("local_first_cleanup_failed")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        maintenance_task: asyncio.Task[None] | None = None
        cleanup_task: asyncio.Task[None] | None = None
        try:
            await reconcile_upload_sessions(database.sessions, storage)
            await scheduler.start()
            maintenance_task = asyncio.create_task(
                maintain_uploads(), name="upload-session-maintenance"
            )
            if resolved_settings.local_first_cleanup_enabled:
                cleanup_task = asyncio.create_task(
                    maintain_local_first_assets(), name="local-first-asset-cleanup"
                )
            logger.info(
                "application_started",
                extra={
                    "event_data": {
                        **resolved_settings.safe_log_context(),
                        "scheduler_status": scheduler.status,
                    }
                },
            )
            yield
        finally:
            if maintenance_task is not None:
                maintenance_task.cancel()
                try:
                    await maintenance_task
                except asyncio.CancelledError:
                    pass
            if cleanup_task is not None:
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    pass
            await scheduler.stop()
            await ark_adapter.close()
            await comfy_http_client.aclose()
            await database.close()
            logger.info("application_stopped")

    app = FastAPI(
        title="Clothes Model Backend",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.scheduler = scheduler
    app.state.storage = storage
    app.state.workflow_artifacts = workflow_artifacts
    app.state.secret_cipher = secret_cipher
    app.state.provider_registry = provider_registry
    app.state.provider_service = provider_service
    app.state.job_execution = job_execution
    app.state.comfy_http_client = comfy_http_client
    app.add_middleware(RequestContextMiddleware)
    if resolved_settings.cors_allowlist:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.cors_allowlist,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_problem_handlers(app)
    register_routes(app)
    if resolved_settings.web_static_root is not None:
        app.mount(
            "/",
            SpaStaticFiles(directory=resolved_settings.web_static_root, html=True),
            name="web-admin",
        )
    return app
