import httpx

from app.config.settings import Settings
from app.domain.exceptions import ArtworkUnavailableError
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface


class HttpArtworkDownloader(ArtworkDownloaderInterface):
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        """
        Create a downloader that fetches artwork images over HTTP.

        Args:
            transport: Optional httpx transport, used by tests to stub responses.
        """
        self._transport = transport
        self._timeout = Settings().ARTWORK_TIMEOUT_SECONDS

    async def download(self, url: str) -> bytes:
        """
        Download an image over HTTP.

        Args:
            url: URL of the image.

        Returns:
            The raw image content.

        Raises:
            ArtworkUnavailableError: If the request fails or doesn't return 2xx.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ArtworkUnavailableError(
                f"download failed: HTTP {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ArtworkUnavailableError(
                f"download failed: {type(e).__name__}"
            ) from e
        return response.content
