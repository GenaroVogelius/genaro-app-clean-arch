import httpx

from app.config.settings import get_settings
from app.domain.ingestion import ArtworkUnavailableError
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.infrastructure.providers.http_client import use_http_client


class HttpArtworkDownloader(ArtworkDownloaderInterface):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """
        Create a downloader that fetches artwork images over HTTP.

        Args:
            client: Shared client the app keeps open, reusing its connections
                across downloads. When None, each download opens its own client.
            transport: Optional httpx transport of the per-download client, used
                by tests to stub responses. Ignored when a client is given.
        """
        self._client = client
        self._transport = transport
        self._timeout = get_settings().ARTWORK_TIMEOUT_SECONDS

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
            async with use_http_client(self._client, self._transport) as client:
                response = await client.get(
                    url, timeout=self._timeout, follow_redirects=True
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ArtworkUnavailableError(
                f"download failed: HTTP {e.response.status_code}"
            ) from e
        except httpx.HTTPError as e:
            raise ArtworkUnavailableError(f"download failed: {type(e).__name__}") from e
        return response.content
