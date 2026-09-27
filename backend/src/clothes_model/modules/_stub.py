"""Shared transport helper for Phase 1 route stubs."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from fastapi import APIRouter, Depends

from clothes_model.core.problems import FeatureNotImplementedProblem
from clothes_model.generated.models import ProblemDetails
from clothes_model.modules.auth.http import require_admin, require_app


@dataclass(frozen=True, slots=True)
class StubRoute:
    path: str
    method: str
    operation_id: str


def add_stub_routes(router: APIRouter, routes: Sequence[StubRoute]) -> None:
    for route in routes:
        router.add_api_route(
            route.path,
            _stub_endpoint(route.operation_id),
            methods=[route.method],
            operation_id=route.operation_id,
            name=route.operation_id,
            responses={501: {"model": ProblemDetails}},
            dependencies=[Depends(require_admin if "/admin/" in route.path else require_app)],
        )


def _stub_endpoint(operation_id: str) -> Callable[[], Awaitable[None]]:
    async def endpoint() -> None:
        raise FeatureNotImplementedProblem(operation_id)

    endpoint.__name__ = operation_id
    return endpoint
