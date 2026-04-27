"""Request-scoped middleware: request ID generation + log context binding.

RequestIDMiddleware reads X-Request-ID if the client supplied one, otherwise
mints a UUID4. It stores the id in a contextvar so every log record emitted
during the request carries it, and echoes the id back in the response header
so callers / upstream proxies can correlate.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from logging_config import bind_request, request_id_var, route_var

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        rid = incoming if _looks_like_uuid(incoming) else str(uuid.uuid4())

        # Route template if matched by starlette, else raw path.
        route_path = request.url.path

        rid_token = request_id_var.set(rid)
        route_token = route_var.set(route_path)
        bind_request(rid, route_path)

        # Expose on request.state for handlers / sentry scope.
        request.state.request_id = rid

        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(rid_token)
            route_var.reset(route_token)

        response.headers[REQUEST_ID_HEADER] = rid
        return response


def _looks_like_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
