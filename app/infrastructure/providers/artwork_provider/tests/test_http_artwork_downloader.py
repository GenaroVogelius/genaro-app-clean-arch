import httpx
import pytest

from app.domain.ingestion import ArtworkUnavailableError
from app.infrastructure.providers.artwork_provider.http_artwork_downloader import (
    HttpArtworkDownloader,
)

URL = "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"


def downloader_returning(response: httpx.Response) -> HttpArtworkDownloader:
    """Build a downloader whose every request gets the given response."""
    return HttpArtworkDownloader(
        transport=httpx.MockTransport(lambda request: response)
    )


@pytest.mark.asyncio
async def test_download_returns_image_bytes() -> None:
    downloader = downloader_returning(httpx.Response(200, content=b"image-bytes"))

    assert await downloader.download(URL) == b"image-bytes"


@pytest.mark.asyncio
async def test_download_raises_on_error_status() -> None:
    downloader = downloader_returning(httpx.Response(404))

    with pytest.raises(ArtworkUnavailableError, match="HTTP 404"):
        await downloader.download(URL)


@pytest.mark.asyncio
async def test_download_raises_on_transport_error() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    downloader = HttpArtworkDownloader(transport=httpx.MockTransport(fail))

    with pytest.raises(ArtworkUnavailableError, match="ConnectError"):
        await downloader.download(URL)


@pytest.mark.asyncio
async def test_download_uses_shared_client_and_follows_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/moved.jpg":
            return httpx.Response(301, headers={"Location": URL})
        return httpx.Response(200, content=b"image-bytes")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        downloader = HttpArtworkDownloader(client=client)

        content = await downloader.download("https://is1-ssl.mzstatic.com/moved.jpg")

        assert content == b"image-bytes"
        assert not client.is_closed
