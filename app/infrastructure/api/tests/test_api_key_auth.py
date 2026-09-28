from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.domain.interfaces.logger import LoggerInterface
from app.infrastructure.api.security import ApiKeyAuth

API_KEY = "secret-key"


class FakeLogger(LoggerInterface):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        pass

    def debug(self, message: str) -> None:
        pass

    def critical(self, message: str) -> None:
        pass


def client_for(auth: ApiKeyAuth) -> TestClient:
    """Build a test client with a single route guarded by the given auth."""
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(auth)])
    async def protected():
        return {"ok": True}

    return TestClient(app)


def enabled_auth(logger: FakeLogger | None = None) -> ApiKeyAuth:
    """Build an enabled auth accepting API_KEY."""
    return ApiKeyAuth(enabled=True, api_key=API_KEY, logger=logger or FakeLogger())


def test_lets_request_through_when_disabled() -> None:
    client = client_for(ApiKeyAuth(enabled=False, api_key=None, logger=FakeLogger()))

    assert client.get("/protected").status_code == 200


def test_lets_request_through_with_valid_key() -> None:
    client = client_for(enabled_auth())

    response = client.get("/protected", headers={"X-API-Key": API_KEY})

    assert response.status_code == 200


def test_returns_401_when_key_is_missing() -> None:
    client = client_for(enabled_auth())

    response = client.get("/protected")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "ApiKey"


def test_returns_401_when_key_is_wrong() -> None:
    client = client_for(enabled_auth())

    response = client.get("/protected", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401


def test_returns_401_and_logs_when_no_key_is_configured() -> None:
    logger = FakeLogger()
    client = client_for(ApiKeyAuth(enabled=True, api_key=None, logger=logger))

    response = client.get("/protected", headers={"X-API-Key": "anything"})

    assert response.status_code == 401
    assert logger.errors == ["AUTH is enabled but API_KEY is not configured"]
