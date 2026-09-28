from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

_EXEMPT_MARKER = "_rate_limit_exempt"


def build_limiter(limit: str, enabled: bool) -> Limiter:
    """
    Build a limiter that counts every request of a client IP against one
    shared bucket, whatever endpoint it calls.

    Args:
        limit: The limit in slowapi/limits notation, e.g. "10/minute".
        enabled: Whether the limit is enforced. When False, every request is
            let through.

    Returns:
        The limiter, which adds Retry-After and X-RateLimit-* headers.
    """
    return Limiter(
        key_func=get_remote_address,
        application_limits=[limit],
        headers_enabled=True,
        enabled=enabled,
    )


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Build the 429 response returned when a client goes over the limit."""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Rate limit exceeded",
            "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        },
    )
    # The middleware leaves header injection to the handler on a 429; slowapi's
    # own handler uses this same method to add Retry-After and X-RateLimit-*.
    return request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )


def rate_limit_exempt[F: Callable[..., Any]](endpoint: F) -> F:
    """
    Mark an endpoint so setup_rate_limiting keeps it out of the limit.

    Apply it below the route decorator, so the router registers the marked
    function. Meant for probes such as health checks, which an orchestrator
    calls on a schedule and must never answer 429.

    Args:
        endpoint: The route function to exempt.

    Returns:
        The same function, marked.
    """
    setattr(endpoint, _EXEMPT_MARKER, True)
    return endpoint


def setup_rate_limiting(app: FastAPI, limiter: Limiter) -> None:
    """
    Enforce the limiter on every route of the app except the docs routes and
    the endpoints marked with rate_limit_exempt.

    Call it before adding CORSMiddleware, so CORS stays the outermost
    middleware: 429 responses get CORS headers and preflight requests are
    answered without counting against the limit.

    Args:
        app: The app to protect. Its routes must already be registered; FastAPI
            registers the docs routes when the app is created.
        limiter: The limiter to enforce.
    """
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        rate_limit_exceeded_handler,  # type: ignore[arg-type]
    )
    # Not SlowAPIASGIMiddleware: it re-sends the response start on every body
    # chunk, which breaks streaming responses such as the CSV export.
    app.add_middleware(SlowAPIMiddleware)
    _exempt_routes(app, limiter)


def _exempt_routes(app: FastAPI, limiter: Limiter) -> None:
    """
    Keep the OpenAPI schema, Swagger UI, ReDoc and every endpoint marked with
    rate_limit_exempt out of the limit.
    """
    docs_paths = {
        app.openapi_url,
        app.docs_url,
        app.swagger_ui_oauth2_redirect_url,
        app.redoc_url,
    } - {None}
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        is_docs = getattr(route, "path", None) in docs_paths
        if is_docs or getattr(endpoint, _EXEMPT_MARKER, False):
            limiter.exempt(endpoint)
