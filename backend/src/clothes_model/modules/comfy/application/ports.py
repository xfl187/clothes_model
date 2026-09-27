"""Persistence ports for the singleton physical ComfyUI node."""

from typing import Protocol

from clothes_model.core.persistence import UnitOfWork
from clothes_model.modules.comfy.domain import ComfyNodeConfig


class ComfyNodeRepository(Protocol):
    async def get(self) -> ComfyNodeConfig | None: ...

    async def save(self, config: ComfyNodeConfig) -> None: ...


class ComfyUnitOfWork(UnitOfWork, Protocol):
    @property
    def comfy_node(self) -> ComfyNodeRepository: ...

