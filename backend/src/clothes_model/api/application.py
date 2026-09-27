"""FastAPI application factory and lifecycle."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clothes_model import __version__
from clothes_model.api.middleware import RequestContextMiddleware
from clothes_model.api.routes import register_routes
from clothes_model.api.static_web import SpaStaticFiles
from clothes_model.core.config import Settings, get_settings
from clothes_model.core.logging import configure_logging, get_logger
from clothes_model.core.problems import register_problem_handlers
from clothes_model.infrastructure.database import create_database_runtime
from clothes_model.infrastructure.scheduler import (
    NoOpJobSource,
    NoOpScheduler,
    SchedulerCoordinator,
)
from clothes_model.infrastructure.security import (
    AesGcmSecretCipher,
    SecretCryptoError,
    load_master_key,
)
from clothes_model.infrastructure.storage import LocalFileStorage, reconcile_upload_sessions
from clothes_model.modules.providers.infrastructure import FakeImageEditAdapter, ProviderRegistry


def _load_secret_cipher(settings: Settings) -> AesGcmSecretCipher | None:
    if settings.encryption_master_key_file is None:
        return None
    try:
        return AesGcmSecretCipher(load_master_key(settings.encryption_master_key_file))
    except SecretCryptoError:
        return None


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated application instance for runtime and tests."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    logger = get_logger(__name__)
    database = create_database_runtime(
        resolved_settings.database_url,
        resolved_settings.sqlite_busy_timeout_ms,
    )
    scheduler = SchedulerCoordinator(
        enabled=resolved_settings.scheduler_enabled,
        lock_path=resolved_settings.instance_lock_path,
        scheduler=NoOpScheduler(NoOpJobSource()),
    )
    storage = LocalFileStorage(resolved_settings.storage_root)
    secret_cipher = _load_secret_cipher(resolved_settings)
    provider_registry = ProviderRegistry(
        [FakeImageEditAdapter()], environment=resolved_settings.environment
    )

    async def maintain_uploads() -> None:
        while True:
            await asyncio.sleep(resolved_settings.upload_maintenance_interval_seconds)
            try:
                await reconcile_upload_sessions(database.sessions, storage)
            except Exception:
                logger.exception("upload_maintenance_failed")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        maintenance_task: asyncio.Task[None] | None = None
        try:
            await reconcile_upload_sessions(database.sessions, storage)
            await scheduler.start()
            maintenance_task = asyncio.create_task(
                maintain_uploads(), name="upload-session-maintenance"
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
            await scheduler.stop()
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
    app.state.secret_cipher = secret_cipher
    app.state.provider_registry = provider_registry
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
