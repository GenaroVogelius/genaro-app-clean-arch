import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.infrastructure.api.rate_limit import (
    build_limiter,
    rate_limit_exempt,
    setup_rate_limiting,
)

pytestmark = pytest.mark.rate_limit

LIMIT = "2/minute"
STREAM_CHUNKS = [b"a,b\n", b"1,2\n", b"3,4\n"]


def client_for(enabled: bool = True) -> TestClient:
    """
    Build a test client for a small app rate limited to LIMIT.

    Args:
        enabled: Whether the limiter enforces the limit.

    Returns:
        A client for an app with two JSON routes, a streaming route and a
        route marked with rate_limit_exempt.
        Each client gets its own limiter, so no counts leak between tests.
    """
    app = FastAPI()

    @app.get("/first")
    async def first():
        return {"ok": True}

    @app.get("/second")
    async def second():
        return {"ok": True}

    @app.get("/stream")
    async def stream():
        async def chunks():
            for chunk in STREAM_CHUNKS:
                yield chunk

        return StreamingResponse(chunks(), media_type="text/csv")

    @app.get("/health")
    @rate_limit_exempt
    async def health():
        return {"status": "ok"}

    setup_rate_limiting(app, build_limiter(LIMIT, enabled))
    return TestClient(app)


def test_request_over_the_limit_gets_429_with_retry_after():
    client = client_for()

    assert client.get("/first").status_code == 200
    assert client.get("/first").status_code == 200
    response = client.get("/first")

    assert response.status_code == 429
    assert response.json() == {"error": "Rate limit exceeded", "status_code": 429}
    assert "Retry-After" in response.headers


def test_allowed_responses_carry_rate_limit_headers():
    client = client_for()

    response = client.get("/first")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert response.headers["X-RateLimit-Remaining"] == "1"


def test_limit_is_shared_across_endpoints():
    client = client_for()

    assert client.get("/first").status_code == 200
    assert client.get("/second").status_code == 200

    assert client.get("/first").status_code == 429
    assert client.get("/second").status_code == 429


def test_docs_routes_are_exempt_and_do_not_use_the_budget():
    client = client_for()

    for _ in range(5):
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200

    assert client.get("/first").status_code == 200
    assert client.get("/first").status_code == 200
    assert client.get("/first").status_code == 429


def test_marked_routes_are_exempt_and_do_not_use_the_budget():
    client = client_for()

    for _ in range(5):
        assert client.get("/health").status_code == 200

    assert client.get("/first").status_code == 200
    assert client.get("/first").status_code == 200
    assert client.get("/first").status_code == 429


def test_marked_routes_answer_after_the_budget_is_spent():
    client = client_for()

    client.get("/first")
    client.get("/first")
    assert client.get("/first").status_code == 429

    assert client.get("/health").status_code == 200


def test_disabled_limiter_never_rejects():
    client = client_for(enabled=False)

    for _ in range(5):
        assert client.get("/first").status_code == 200


def test_streaming_response_is_sent_whole():
    client = client_for()

    response = client.get("/stream")

    assert response.status_code == 200
    assert response.content == b"".join(STREAM_CHUNKS)
