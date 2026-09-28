import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config.settings import Settings
from app.domain.interfaces.logger import LoggerInterface

# Header clients send the API key in; also exposed in the OpenAPI docs.
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class ApiKeyAuth:
    """FastAPI dependency that rejects requests without a valid API key."""

    def __init__(self, enabled: bool, api_key: str | None, logger: LoggerInterface):
        """
        Args:
            enabled: Whether requests must carry a valid API key. When False,
                every request is let through.
            api_key: The only key accepted. When auth is enabled but no key is
                configured, every request is rejected.
            logger: Logger used to report a missing key configuration.
        """
        self._enabled = enabled
        self._api_key = api_key
        self._logger = logger

    @classmethod
    def from_settings(cls, settings: Settings, logger: LoggerInterface) -> "ApiKeyAuth":
        """
        Build the dependency from the app settings.

        Args:
            settings: Settings holding the AUTH flag and the API_KEY.
            logger: Logger used to report a missing key configuration.

        Returns:
            The dependency configured as the settings say.
        """
        return cls(enabled=settings.AUTH, api_key=settings.API_KEY, logger=logger)

    async def __call__(
        self, provided_key: str | None = Security(API_KEY_HEADER)
    ) -> None:
        """
        Let the request through when auth is disabled or the key is valid.

        Args:
            provided_key: The key sent in the X-API-Key header, if any.

        Raises:
            HTTPException: 401 when the key is missing or invalid, or when auth
                is enabled but no API key is configured.
        """
        if not self._enabled:
            return
        if not self._api_key:
            self._logger.error("AUTH is enabled but API_KEY is not configured")
            raise self._unauthorized()
        if provided_key is None or not secrets.compare_digest(
            provided_key.encode(), self._api_key.encode()
        ):
            raise self._unauthorized()

    @staticmethod
    def _unauthorized() -> HTTPException:
        """Build the 401 response returned for any rejected request."""
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
