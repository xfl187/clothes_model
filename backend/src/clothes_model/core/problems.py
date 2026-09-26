"""Uniform RFC 9457-style Problem Details responses."""

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AnyUrl

from clothes_model.core.logging import current_trace_id, get_logger
from clothes_model.generated.models import FieldError, ProblemDetails

logger = get_logger(__name__)


def _empty_context() -> dict[str, Any]:
    return {}


@dataclass(slots=True)
class AppProblem(Exception):
    status: int
    code: str
    title: str
    detail: str
    retryable: bool = False
    context: dict[str, Any] = field(default_factory=_empty_context)


class FeatureNotImplementedProblem(AppProblem):
    def __init__(self, operation_id: str) -> None:
        super().__init__(
            status=501,
            code="not_implemented",
            title="功能尚未实现",
            detail="该接口已建立工程契约，但业务逻辑将在后续阶段实现。",
            context={"operation_id": operation_id},
        )


def _response(problem: ProblemDetails) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppProblem)
    async def handle_app_problem(_: Request, problem: AppProblem) -> JSONResponse:
        return _response(
            ProblemDetails(
                type=AnyUrl(f"https://clothes-model.local/problems/{problem.code}"),
                title=problem.title,
                status=problem.status,
                code=problem.code,
                detail=problem.detail,
                trace_id=current_trace_id(),
                retryable=problem.retryable,
                field_errors=[],
                context=problem.context,
            )
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        field_errors = [
            FieldError(
                field=".".join(str(part) for part in item["loc"]),
                code=str(item["type"]),
                detail="请求字段无效。",
            )
            for item in error.errors()
        ]
        return _response(
            ProblemDetails(
                type=AnyUrl("https://clothes-model.local/problems/validation-error"),
                title="请求无效",
                status=422,
                code="validation_error",
                detail="一个或多个请求字段未通过验证。",
                trace_id=current_trace_id(),
                retryable=False,
                field_errors=field_errors,
                context={},
            )
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, error: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            extra={"event_data": {"exception_type": type(error).__name__}},
        )
        return _response(
            ProblemDetails(
                type=AnyUrl("https://clothes-model.local/problems/internal-error"),
                title="服务器错误",
                status=500,
                code="internal_error",
                detail="服务器暂时无法完成请求。",
                trace_id=current_trace_id(),
                retryable=False,
                field_errors=[],
                context={},
            )
        )
