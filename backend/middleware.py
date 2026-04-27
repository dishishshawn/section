"""Request-scoped middleware: request ID generation + log context binding.

RequestIDMiddleware reads X-Request-ID if the client supplied one, otherwise
mints a UUID4. It stores the id in a contextvar so every log record emitted
during the request carries it, and echoes the id back in the response header
so callers / upstream proxies can correlate.
"""

from __future__ import annotations

import uuid
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from logging_config import bind_request, request_id_var, route_var

REQUEST_ID_HEADER = "X-Request-ID"

# 1 year, matches the HSTS preload-list eligibility threshold. includeSubDomains
# + preload are required for inclusion at hstspreload.org; opt-out by removing
# preload before submission if a non-HTTPS subdomain ever needs to ship.
HSTS_VALUE = "max-age=31536000; includeSubDomains; preload"


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    """Force HTTPS in production: 301 plain HTTP to HTTPS and emit HSTS.

    Honors ``X-Forwarded-Proto`` so deployments behind a TLS-terminating
    proxy (ALB, nginx, Cloud Run, ``uvicorn --proxy-headers``) detect the
    real client scheme. Disabled when ``enabled`` is False so dev/test stay
    HTTP-friendly.

    A small skip list keeps cheap load-balancer health probes plain-HTTP.
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        skip_paths: Iterable[str] = ("/health",),
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.skip_paths = set(skip_paths)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # X-Forwarded-Proto may be a comma list ("https, http") when the
        # request crosses multiple proxies. The leftmost entry is what the
        # original client spoke — the one we care about for redirect.
        forwarded = request.headers.get("x-forwarded-proto")
        if forwarded:
            scheme = forwarded.split(",")[0].strip().lower()
        else:
            scheme = request.url.scheme.lower()

        path = request.url.path
        if scheme != "https" and path not in self.skip_paths:
            target = request.url.replace(scheme="https")
            return RedirectResponse(url=str(target), status_code=301)

        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = HSTS_VALUE
        return response


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
