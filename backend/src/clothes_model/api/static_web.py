"""Optional deployment-only static Web Admin mount."""

from collections.abc import MutableMapping
from typing import Any

from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class SpaStaticFiles(StaticFiles):
    """Serve built files and fall back to index.html for client-side routes."""

    async def get_response(
        self,
        path: str,
        scope: MutableMapping[str, Any],
    ) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHttpException as error:
            if error.status_code != 404 or scope.get("method") not in {"GET", "HEAD"}:
                raise
        else:
            if response.status_code != 404 or scope.get("method") not in {"GET", "HEAD"}:
                return response

        return await super().get_response("index.html", scope)
