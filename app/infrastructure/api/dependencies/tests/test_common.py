from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.infrastructure.api.dependencies.common import (
    HttpClientDep,
    get_api_key_auth,
    get_settings,
    require_api_key,
)
from app.infrastructure.api.security import ApiKeyAuth
from app.infrastructure.logger import logger

API_KEY = "secret-key"


@pytest.fixture(autouse=True)
def clear_caches() -> Iterator[None]:
    """Reset the cached factories so every test builds fresh instances."""
    get_settings.cache_clear()
    get_api_key_auth.cache_clear()
    yield
    get_settings.cache_clear()
    get_api_key_auth.cache_clear()


def client_for(auth: ApiKeyAuth) -> TestClient:
    """
    Build a test client with a single route guarded by require_api_key, whose
    API key check is overridden with the given auth.
    """
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_api_key)])
    async def protected():
        return {"ok": True}

    app.dependency_overrides[get_api_key_auth] = lambda: auth
    return TestClient(app)


def test_settings_are_built_once() -> None:
    assert get_settings() is get_settings()


def test_api_key_auth_is_built_once() -> None:
    assert get_api_key_auth() is get_api_key_auth()


def test_require_api_key_rejects_request_without_key() -> None:
    client = client_for(ApiKeyAuth(enabled=True, api_key=API_KEY, logger=logger))

    assert client.get("/protected").status_code == 401


def test_require_api_key_accepts_valid_key() -> None:
    client = client_for(ApiKeyAuth(enabled=True, api_key=API_KEY, logger=logger))

    response = client.get("/protected", headers={"X-API-Key": API_KEY})

    assert response.status_code == 200


def test_http_client_is_the_one_held_by_the_app() -> None:
    app = FastAPI()
    shared = object()
    app.state.http_client = shared

    @app.get("/client")
    async def client_route(client: HttpClientDep):
        return {"shared": client is shared}

    assert TestClient(app).get("/client").json() == {"shared": True}
