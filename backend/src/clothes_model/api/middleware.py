"""Request correlation middleware."""

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from clothes_model.core.logging import reset_request_context, set_request_context

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a safe request/trace identifier to every request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        candidate = request.headers.get("x-request-id", "")
        request_id = candidate if _SAFE_REQUEST_ID.fullmatch(candidate) else uuid.uuid4().hex
        token = set_request_context(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_context(token)
