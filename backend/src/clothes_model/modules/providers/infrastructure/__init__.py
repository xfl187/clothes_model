"""Provider infrastructure adapters."""

from clothes_model.modules.providers.infrastructure.fake import FakeImageEditAdapter
from clothes_model.modules.providers.infrastructure.registry import ProviderRegistry

__all__ = ["FakeImageEditAdapter", "ProviderRegistry"]
