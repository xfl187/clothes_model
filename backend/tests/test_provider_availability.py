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
from clothes_model.modules.providers.infrastructure import FakeImageEditAdapter, ProviderRegistry
from clothes_model.modules.providers.infrastructure.fake import FAKE_ADAPTER_TYPE
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
            assessment = await service.assess_availability_for(config, revision)
            assert assessment.status == "available"
            assert assessment.unavailable_reason is None

            without_key = ProviderConfigService(
                lambda: SqlAlchemyUnitOfWork(runtime.sessions), registry, None
            )
            assert (
                await without_key.availability_for(config, revision)
                == "unavailable_configuration"
            )
            missing_key = await without_key.assess_availability_for(config, revision)
            assert missing_key.unavailable_reason == (
                "服务端加密主密钥未配置，无法读取 Provider 凭据。"
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
            rotated = await rotated_key.assess_availability_for(config, revision)
            assert rotated.unavailable_reason == (
                "Provider 凭据无法用当前服务端主密钥解密，请管理员重新保存 API Key。"
            )
        finally:
            await runtime.close()

    asyncio.run(run())


def test_availability_allows_adapters_that_do_not_use_provider_credentials() -> None:
    config = ProviderConfig(
        id=str(uuid4()),
        display_name="Offline fixture",
        provider_type="llm_image_edit",
        state="active",
        created_at=now(),
        updated_at=now(),
    )
    revision = ProviderConfigRevision(
        id=str(uuid4()),
        provider_id=config.id,
        revision=1,
        adapter_type=FAKE_ADAPTER_TYPE,
        endpoint="https://fixture.invalid",
        model="fixture",
        timeout_seconds=30,
        capabilities_json="{}",
        vendor_parameters_json='{"scenario":"offline"}',
        created_at=now(),
    )
    registry = ProviderRegistry([FakeImageEditAdapter()], environment="test")
    service = ProviderConfigService(lambda: None, registry, None)  # type: ignore[arg-type]

    assessment = asyncio.run(service.assess_availability_for(config, revision))

    assert assessment.status == "temporarily_offline"
    assert assessment.unavailable_reason == "Provider 暂时离线，任务可以排队等待恢复。"
