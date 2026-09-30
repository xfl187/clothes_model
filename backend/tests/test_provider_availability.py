import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from clothes_model.infrastructure.database import SqlAlchemyUnitOfWork, create_database_runtime
from clothes_model.infrastructure.database.migrations import upgrade_database
from clothes_model.infrastructure.security import AesGcmSecretCipher
from clothes_model.modules.providers.application.services import (
    SECRET_PURPOSE,
    ProviderConfigService,
)
from clothes_model.modules.providers.domain import ProviderConfig, ProviderConfigRevision
from clothes_model.modules.providers.infrastructure import ProviderRegistry
from clothes_model.modules.providers.infrastructure.volcengine_ark import (
    ARK_ADAPTER_TYPE,
    ARK_BASE_URL,
    ARK_MODEL,
    VolcengineArkSeedreamAdapter,
)


def now() -> datetime:
    return datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def test_availability_decrypts_configured_credential(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'availability.db').as_posix()}"
    upgrade_database(database_url, tmp_path / "migration.lock")
    cipher = AesGcmSecretCipher(os.urandom(32))
    provider_id, revision_id = str(uuid4()), str(uuid4())
    envelope = cipher.encrypt("ark-test-key", purpose=SECRET_PURPOSE, record_id=provider_id)

    async def run() -> None:
        runtime = create_database_runtime(database_url, 5000)
        try:
            async with SqlAlchemyUnitOfWork(runtime.sessions) as uow:
                await uow.provider_configs.add_config(
                    ProviderConfig(
                        id=provider_id,
                        display_name="Ark",
                        provider_type="llm_image_edit",
                        state="active",
                        created_at=now(),
                        updated_at=now(),
                        secret_envelope=envelope,
                        secret_updated_at=now(),
                    )
                )
                await uow.provider_configs.add_revision(
                    ProviderConfigRevision(
                        id=revision_id,
                        provider_id=provider_id,
                        revision=1,
                        adapter_type=ARK_ADAPTER_TYPE,
                        endpoint=ARK_BASE_URL,
                        model=ARK_MODEL,
                        timeout_seconds=30,
                        capabilities_json="{}",
                        created_at=now(),
                    )
                )
                await uow.commit()

            registry = ProviderRegistry([VolcengineArkSeedreamAdapter()], environment="test")
            service = ProviderConfigService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions), registry, cipher
            )
            config = await service.get(provider_id)
            revision = await service.current_revision(provider_id)
            assert config is not None and revision is not None
            # A configured credential must be decrypted before availability is judged.
            assert await service.availability_for(config, revision) == "available"

            without_key = ProviderConfigService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions), registry, None
            )
            assert (
                await without_key.availability_for(config, revision)
                == "unavailable_configuration"
            )

            rotated_key = ProviderConfigService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions),
                registry,
                AesGcmSecretCipher(os.urandom(32)),
            )
            assert (
                await rotated_key.availability_for(config, revision)
                == "unavailable_configuration"
            )
        finally:
            await runtime.close()

    asyncio.run(run())
