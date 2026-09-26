import httpx
import pytest

from app.domain.aggregates.podcast import Podcast
from app.domain.exceptions import ExternalServiceError, NotAPodcastError
from app.infrastructure.logger import logger
from app.infrastructure.providers.itunes_provider.itunes_provider import ITunesProvider
from app.infrastructure.utils.testing.vcr import get_vcr_for_test

vcr = get_vcr_for_test(__file__)

THE_DAILY_ID = 1200361736


@pytest.mark.asyncio
async def test_lookup_by_id_returns_podcast() -> None:
    with vcr.use_cassette("lookup_podcast.yaml"):
        result = await ITunesProvider().lookup_by_id(THE_DAILY_ID)

    logger.info(f"Podcast feed URL: {result}")
    assert isinstance(result, Podcast)
    assert result.podcast_id == THE_DAILY_ID
    assert result.feed_url is not None


@pytest.mark.asyncio
async def test_lookup_by_id_returns_none_when_not_found() -> None:
    with vcr.use_cassette("lookup_not_found.yaml"):
        result = await ITunesProvider().lookup_by_id(999999999999)

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(
            200,
            json={
                "resultCount": 1,
                "results": [
                    {
                        "wrapperType": "track",
                        "kind": "podcast",
                        "trackId": 1,
                        "trackName": "Something",
                        # artistName missing: a podcast requires an author.
                    }
                ],
            },
        ),
    ],
)
async def test_lookup_by_id_raises_external_service_error(
    response: httpx.Response,
) -> None:
    transport = httpx.MockTransport(lambda request: response)

    with pytest.raises(ExternalServiceError):
        await ITunesProvider(transport=transport).lookup_by_id(1)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["song", "unknown"])
async def test_lookup_by_id_raises_not_a_podcast_error_for_other_kinds(
    kind: str,
) -> None:
    response = httpx.Response(
        200,
        json={
            "resultCount": 1,
            "results": [
                {
                    "wrapperType": "track",
                    "kind": kind,
                    "trackId": 1,
                    "trackName": "Upside Down",
                    "artistName": "Jack Johnson",
                }
            ],
        },
    )
    transport = httpx.MockTransport(lambda request: response)

    with pytest.raises(NotAPodcastError):
        await ITunesProvider(transport=transport).lookup_by_id(1)
