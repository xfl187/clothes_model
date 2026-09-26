"""Persistence ports safe for application and domain dependencies."""

from types import TracebackType
from typing import Protocol, Self


class Repository[T](Protocol):
    """Minimal repository boundary extended by future feature modules."""

    async def add(self, entity: T) -> None: ...

    async def get(self, entity_id: object) -> T | None: ...


class PersistenceConflict(RuntimeError):
    """A database constraint rejected a competing or invalid write."""


class UnitOfWork(Protocol):
    """Explicit transaction boundary independent of SQLAlchemy and SQLite."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
