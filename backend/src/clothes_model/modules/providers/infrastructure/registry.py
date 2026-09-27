"""Adapter registry that fails closed on fake adapters in production."""

from collections.abc import Sequence

from clothes_model.modules.providers.application.ports import ProviderAdapter
from clothes_model.modules.providers.domain import ProviderError
from clothes_model.modules.providers.infrastructure.fake import FAKE_ADAPTER_TYPE

FAKE_ADAPTER_PREFIX = "fake"


class ProviderRegistry:
    def __init__(
        self,
        adapters: Sequence[ProviderAdapter],
        *,
        environment: str = "development",
    ) -> None:
        self._adapters = {adapter.adapter_type: adapter for adapter in adapters}
        self._environment = environment

    @property
    def adapter_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def resolve(self, adapter_type: str) -> ProviderAdapter:
        if self._environment == "production" and adapter_type.startswith(FAKE_ADAPTER_PREFIX):
            raise ProviderError(
                "invalid_configuration",
                "fake_adapter_forbidden",
                "生产环境不允许使用测试 Provider。",
            )
        adapter = self._adapters.get(adapter_type)
        if adapter is None:
            raise ProviderError(
                "invalid_configuration",
                "unknown_adapter",
                "未注册的 Provider 适配器。",
            )
        return adapter

    def ensure_production_safe(self) -> None:
        if self._environment != "production":
            return
        if any(name.startswith(FAKE_ADAPTER_PREFIX) for name in self._adapters):
            raise ProviderError(
                "invalid_configuration",
                "fake_adapter_forbidden",
                "生产环境不允许使用测试 Provider。",
            )


__all__ = ["FAKE_ADAPTER_TYPE", "ProviderRegistry"]
