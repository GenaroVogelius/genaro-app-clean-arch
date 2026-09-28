from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


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


def setup_rate_limiting(app: FastAPI, limiter: Limiter) -> None:
    """
    Enforce the limiter on every route of the app except the docs routes.

    Call it before adding CORSMiddleware, so CORS stays the outermost
    middleware: 429 responses get CORS headers and preflight requests are
    answered without counting against the limit.

    Args:
        app: The app to protect. Its docs routes must already be registered,
            which FastAPI does when the app is created.
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
    _exempt_docs_routes(app, limiter)


def _exempt_docs_routes(app: FastAPI, limiter: Limiter) -> None:
    """Keep the OpenAPI schema, Swagger UI and ReDoc out of the limit."""
    docs_paths = {
        app.openapi_url,
        app.docs_url,
        app.swagger_ui_oauth2_redirect_url,
        app.redoc_url,
    } - {None}
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None and getattr(route, "path", None) in docs_paths:
            limiter.exempt(endpoint)
