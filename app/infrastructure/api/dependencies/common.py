from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, Request, Security

from app.config.settings import Settings, get_settings
from app.domain.interfaces.logger import LoggerInterface
from app.infrastructure.api.security import API_KEY_HEADER, ApiKeyAuth
from app.infrastructure.logger import logger


def get_logger() -> LoggerInterface:
    """
    Get the logger injected into the use cases.

    Returns:
        The app logger.
    """
    return logger


def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Get the HTTP client shared by every outbound adapter.

    Args:
        request: The current request, whose app holds the client.

    Returns:
        The client opened by the app's lifespan and closed on shutdown.
    """
    return request.app.state.http_client


@lru_cache
def get_api_key_auth() -> ApiKeyAuth:
    """
    Get the API key check guarding the protected routes.

    Returns:
        The check configured from the AUTH and API_KEY settings, built once
        and reused for the life of the process.
    """
    return ApiKeyAuth.from_settings(get_settings(), logger)


async def require_api_key(
    auth: Annotated[ApiKeyAuth, Depends(get_api_key_auth)],
    provided_key: Annotated[str | None, Security(API_KEY_HEADER)],
) -> None:
    """
    Route dependency that lets the request through only with a valid API key.

    Args:
        auth: The API key check to run.
        provided_key: The key sent in the X-API-Key header, if any.

    Raises:
        HTTPException: 401 when the key is rejected.
    """
    await auth(provided_key)


SettingsDep = Annotated[Settings, Depends(get_settings)]
LoggerDep = Annotated[LoggerInterface, Depends(get_logger)]
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
