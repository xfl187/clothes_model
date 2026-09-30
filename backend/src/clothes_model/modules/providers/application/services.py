"""Provider configuration lifecycle and invocation resolution."""

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from clothes_model.infrastructure.security import AesGcmSecretCipher, SecretCryptoError
from clothes_model.modules.providers.domain import (
    ProviderCapabilities,
    ProviderConfig,
    ProviderConfigRevision,
    ProviderDefaultSelection,
    ProviderError,
    ProviderInvocation,
)

SECRET_PURPOSE = "provider_credential"


class ProviderUnitOfWorkFactory(Protocol):
    def __call__(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class ValidationStep:
    key: str
    status: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    status: str
    revision: ProviderConfigRevision
    capabilities: ProviderCapabilities
    steps: tuple[ValidationStep, ...]


def _as_parameters(raw: dict[str, Any] | None) -> dict[str, Any]:
    return dict(raw or {})


class ProviderConfigService:
    def __init__(
        self,
        uow_factory: ProviderUnitOfWorkFactory,
        registry: Any,
        cipher: AesGcmSecretCipher | None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._registry = registry
        self._cipher = cipher
        self._clock = clock or (lambda: datetime.now(UTC))

    def _invocation(
        self,
        config: ProviderConfig,
        revision: ProviderConfigRevision,
        credential: str | None,
    ) -> ProviderInvocation:
        return ProviderInvocation(
            provider_id=config.id,
            config_revision_id=revision.id,
            adapter_type=revision.adapter_type,
            endpoint=revision.endpoint,
            model=revision.model,
            timeout_seconds=revision.timeout_seconds,
            vendor_parameters=json.loads(revision.vendor_parameters_json or "{}"),
            credential=credential,
        )

    def _encrypt(self, provider_id: str, api_key: str | None) -> tuple[str | None, datetime | None]:
        if api_key is None:
            return None, None
        if self._cipher is None:
            raise ProviderError(
                "invalid_configuration",
                "secret_key_unavailable",
                "服务端加密主密钥未配置，无法保存凭据。",
            )
        envelope = self._cipher.encrypt(api_key, purpose=SECRET_PURPOSE, record_id=provider_id)
        return envelope, self._clock()

    async def create(
        self,
        *,
        display_name: str,
        provider_type: str,
        adapter_type: str,
        endpoint: str,
        model: str,
        timeout_seconds: int,
        vendor_parameters: dict[str, Any] | None,
        api_key: str | None,
    ) -> ProviderConfig:
        provider_id = str(uuid4())
        self._registry.resolve(adapter_type)
        envelope, secret_at = self._encrypt(provider_id, api_key)
        now = self._clock()
        config = ProviderConfig(
            id=provider_id,
            display_name=display_name,
            provider_type=provider_type,  # type: ignore[arg-type]
            state="inactive",
            created_at=now,
            updated_at=now,
            secret_envelope=envelope,
            secret_updated_at=secret_at,
        )
        async with self._uow_factory() as uow:
            await uow.provider_configs.add_config(config)
            revision = await self._build_revision(
                config,
                revision_number=1,
                adapter_type=adapter_type,
                endpoint=endpoint,
                model=model,
                timeout_seconds=timeout_seconds,
                vendor_parameters=vendor_parameters,
            )
            await uow.provider_configs.add_revision(revision)
            await uow.commit()
        return config

    async def _build_revision(
        self,
        config: ProviderConfig,
        *,
        revision_number: int,
        adapter_type: str,
        endpoint: str,
        model: str,
        timeout_seconds: int,
        vendor_parameters: dict[str, Any] | None,
    ) -> ProviderConfigRevision:
        adapter = self._registry.resolve(adapter_type)
        revision_id = str(uuid4())
        probe = ProviderInvocation(
            provider_id=config.id,
            config_revision_id=revision_id,
            adapter_type=adapter_type,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout_seconds,
            vendor_parameters=_as_parameters(vendor_parameters),
        )
        capabilities = await adapter.capabilities(probe)
        return ProviderConfigRevision(
            id=revision_id,
            provider_id=config.id,
            revision=revision_number,
            adapter_type=adapter_type,
            endpoint=endpoint,
            model=model,
            timeout_seconds=timeout_seconds,
            capabilities_json=capabilities.to_json(),
            vendor_parameters_json=json.dumps(
                probe.vendor_parameters, separators=(",", ":"), sort_keys=True
            ),
            created_at=self._clock(),
        )

    async def get(self, provider_id: str) -> ProviderConfig | None:
        async with self._uow_factory() as uow:
            return await uow.provider_configs.get_config(provider_id)

    async def list(self) -> list[ProviderConfig]:
        async with self._uow_factory() as uow:
            return await uow.provider_configs.list_configs()

    async def current_revision(self, provider_id: str) -> ProviderConfigRevision | None:
        async with self._uow_factory() as uow:
            return await uow.provider_configs.get_current_revision(provider_id)

    async def delete(self, provider_id: str) -> None:
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            if config.provider_type == "comfyui":
                raise ProviderError(
                    "invalid_configuration",
                    "provider_system_managed",
                    "系统管理的 ComfyUI Provider 不能删除。",
                )
            default = await uow.provider_configs.get_default()
            if default is not None and default.provider_id == provider_id:
                raise ProviderError(
                    "invalid_configuration",
                    "provider_is_default",
                    "默认 Provider 不能删除，请先选择其他默认 Provider。",
                )
            if await uow.provider_configs.has_references(provider_id):
                raise ProviderError(
                    "invalid_configuration",
                    "provider_has_job_history",
                    "Provider 已被任务历史引用，不能删除。",
                )
            await uow.provider_configs.delete_config(provider_id)
            await uow.commit()

    async def archive(self, provider_id: str) -> ProviderConfig:
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            if config.provider_type == "comfyui":
                raise ProviderError(
                    "invalid_configuration",
                    "provider_system_managed",
                    "系统管理的 ComfyUI Provider 不能归档。",
                )
            default = await uow.provider_configs.get_default()
            if default is not None and default.provider_id == provider_id:
                raise ProviderError(
                    "invalid_configuration",
                    "provider_is_default",
                    "默认 Provider 不能归档，请先选择其他默认 Provider。",
                )
            if config.state == "disabled":
                return config
            updated = replace(config, state="disabled", updated_at=self._clock())
            await uow.provider_configs.update_config(updated)
            await uow.commit()
            return updated

    async def restore(self, provider_id: str) -> ProviderConfig:
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            if config.provider_type == "comfyui":
                raise ProviderError(
                    "invalid_configuration",
                    "provider_system_managed",
                    "系统管理的 ComfyUI Provider 不能恢复。",
                )
            if config.state != "disabled":
                raise ProviderError(
                    "invalid_configuration",
                    "provider_not_archived",
                    "Provider 当前未归档。",
                )
            updated = replace(config, state="inactive", updated_at=self._clock())
            await uow.provider_configs.update_config(updated)
            await uow.commit()
            return updated

    async def update(
        self,
        provider_id: str,
        *,
        display_name: str,
        provider_type: str,
        adapter_type: str,
        endpoint: str,
        model: str,
        timeout_seconds: int,
        vendor_parameters: dict[str, Any] | None,
        api_key: str | None,
    ) -> ProviderConfig:
        self._registry.resolve(adapter_type)
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            if config.state == "disabled":
                raise ProviderError(
                    "invalid_configuration", "provider_archived", "请先恢复已归档的 Provider。"
                )
            revisions = await uow.provider_configs.list_revisions(provider_id)
            next_number = (revisions[-1].revision if revisions else 0) + 1
            envelope = config.secret_envelope
            secret_at = config.secret_updated_at
            if api_key is not None:
                envelope, secret_at = self._encrypt(provider_id, api_key)
            updated = ProviderConfig(
                id=provider_id,
                display_name=display_name,
                provider_type=provider_type,  # type: ignore[arg-type]
                state="inactive",
                created_at=config.created_at,
                updated_at=self._clock(),
                secret_envelope=envelope,
                secret_updated_at=secret_at,
            )
            await uow.provider_configs.update_config(updated)
            revision = await self._build_revision(
                updated,
                revision_number=next_number,
                adapter_type=adapter_type,
                endpoint=endpoint,
                model=model,
                timeout_seconds=timeout_seconds,
                vendor_parameters=vendor_parameters,
            )
            await uow.provider_configs.add_revision(revision)
            await uow.commit()
            return updated

    async def resolve_invocation(
        self, provider_id: str, revision_id: str | None = None
    ) -> tuple[ProviderInvocation, ProviderConfig, ProviderConfigRevision]:
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            revision = (
                await uow.provider_configs.get_revision(revision_id)
                if revision_id
                else await uow.provider_configs.get_current_revision(provider_id)
            )
            if revision is None:
                raise ProviderError(
                    "invalid_configuration",
                    "locked_configuration_unavailable",
                    "锁定的 Provider 配置不可用。",
                )
            credential = None
            if config.secret_envelope is not None:
                if self._cipher is None:
                    raise ProviderError(
                        "invalid_configuration",
                        "secret_key_unavailable",
                        "服务端加密主密钥未配置。",
                    )
                credential = self._cipher.decrypt(
                    config.secret_envelope, purpose=SECRET_PURPOSE, record_id=provider_id
                )
            return self._invocation(config, revision, credential), config, revision

    async def availability(self, provider_id: str) -> str:
        invocation, _, _ = await self.resolve_invocation(provider_id)
        adapter = self._registry.resolve(invocation.adapter_type)
        return str(await adapter.availability(invocation))

    async def availability_for(
        self, config: ProviderConfig, revision: ProviderConfigRevision
    ) -> str:
        credential = None
        if config.secret_envelope is not None:
            if self._cipher is None:
                return "unavailable_configuration"
            try:
                credential = self._cipher.decrypt(
                    config.secret_envelope, purpose=SECRET_PURPOSE, record_id=config.id
                )
            except SecretCryptoError:
                return "unavailable_configuration"
        invocation = self._invocation(config, revision, credential)
        adapter = self._registry.resolve(revision.adapter_type)
        return str(await adapter.availability(invocation))

    async def validate(self, provider_id: str) -> ValidationOutcome:
        invocation, config, revision = await self.resolve_invocation(provider_id)
        if config.state == "disabled":
            raise ProviderError(
                "invalid_configuration", "provider_archived", "请先恢复已归档的 Provider。"
            )
        adapter = self._registry.resolve(invocation.adapter_type)
        availability = str(await adapter.availability(invocation))
        capabilities = await adapter.capabilities(invocation)
        steps: list[ValidationStep] = [
            ValidationStep(
                "credentials", "passed" if invocation.credential else "failed",
                None if invocation.credential else "Provider 凭据未配置。",
            ),
            ValidationStep("connection", "passed" if availability == "available" else "failed"),
            ValidationStep(
                "capabilities",
                "passed" if capabilities.verification != "unavailable" else "failed",
            ),
        ]
        passed = availability == "available" and all(step.status == "passed" for step in steps)
        if passed:
            try:
                await adapter.validate(invocation)
            except ProviderError as error:
                steps.append(ValidationStep("generation", "failed", error.detail))
                passed = False
            else:
                steps.extend(
                    (
                        ValidationStep("generation", "passed"),
                        ValidationStep("output_decode", "passed"),
                    )
                )
        if passed:
            updated = ProviderConfig(
                id=config.id,
                display_name=config.display_name,
                provider_type=config.provider_type,
                state="validated",
                created_at=config.created_at,
                updated_at=self._clock(),
                secret_envelope=config.secret_envelope,
                secret_updated_at=config.secret_updated_at,
            )
            async with self._uow_factory() as uow:
                await uow.provider_configs.update_config(updated)
                await uow.commit()
        else:
            steps.append(
                ValidationStep("result", "failed", "Provider 当前不可用或配置无效。")
            )
        return ValidationOutcome(
            status="passed" if passed else "failed",
            revision=revision,
            capabilities=capabilities,
            steps=tuple(steps),
        )

    async def enable(self, provider_id: str) -> ProviderConfig:
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            if config.state == "disabled":
                raise ProviderError(
                    "invalid_configuration", "provider_archived", "请先恢复已归档的 Provider。"
                )
            if config.state not in {"validated", "active"}:
                raise ProviderError(
                    "invalid_configuration",
                    "provider_not_validated",
                    "Provider 必须先通过验证才能启用。",
                )
            updated = ProviderConfig(
                id=config.id,
                display_name=config.display_name,
                provider_type=config.provider_type,
                state="active",
                created_at=config.created_at,
                updated_at=self._clock(),
                secret_envelope=config.secret_envelope,
                secret_updated_at=config.secret_updated_at,
            )
            await uow.provider_configs.update_config(updated)
            await uow.commit()
            return updated

    async def set_default(self, provider_id: str) -> ProviderDefaultSelection:
        async with self._uow_factory() as uow:
            config = await uow.provider_configs.get_config(provider_id)
            if config is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 不存在。"
                )
            if config.state == "disabled":
                raise ProviderError(
                    "invalid_configuration", "provider_archived", "已归档 Provider 不能设为默认。"
                )
            if config.state != "active":
                raise ProviderError(
                    "invalid_configuration",
                    "provider_not_active",
                    "Provider 必须先验证并启用才能设为默认。",
                )
            revision = await uow.provider_configs.get_current_revision(provider_id)
            if revision is None:
                raise ProviderError(
                    "invalid_configuration", "provider_not_found", "Provider 配置缺失。"
                )
            selection = ProviderDefaultSelection(
                id="default",
                provider_id=provider_id,
                config_revision_id=revision.id,
                updated_at=self._clock(),
            )
            await uow.provider_configs.set_default(selection)
            await uow.commit()
            return selection

    async def get_default(self) -> ProviderDefaultSelection | None:
        async with self._uow_factory() as uow:
            return await uow.provider_configs.get_default()
