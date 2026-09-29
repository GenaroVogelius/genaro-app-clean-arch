import httpx
import pytest

from app.domain.common import ExternalServiceError
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.exceptions import NotAPodcastError
from app.domain.podcast.queries import PodcastSearchCriteria, PodcastSearchResult
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


ROCK_CRITERIA = PodcastSearchCriteria(term="rock and roll", limit=10, country="US")


def search_response(*results: dict) -> httpx.Response:
    """Build an iTunes Search API response with the given raw results."""
    return httpx.Response(
        200, json={"resultCount": len(results), "results": list(results)}
    )


def raw_podcast(collection_id: int, **overrides) -> dict:
    """Build a raw iTunes search result of kind podcast."""
    return {
        "wrapperType": "track",
        "kind": "podcast",
        "collectionId": collection_id,
        "trackId": collection_id,
        "collectionName": f"Rock show {collection_id}",
        "artistName": "Some Author",
        **overrides,
    }


@pytest.mark.asyncio
async def test_search_returns_podcasts() -> None:
    with vcr.use_cassette("search_rock_podcasts.yaml"):
        result = await ITunesProvider().search(ROCK_CRITERIA)

    assert isinstance(result, PodcastSearchResult)
    assert 0 < len(result.podcasts) <= ROCK_CRITERIA.limit
    assert all(isinstance(p, Podcast) for p in result.podcasts)
    assert result.fetched == len(result.podcasts) + result.rejected


@pytest.mark.asyncio
async def test_search_sends_podcast_search_params() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return search_response()

    await ITunesProvider(transport=httpx.MockTransport(handler)).search(ROCK_CRITERIA)

    assert requests[0].url.path == "/search"
    assert dict(requests[0].url.params) == {
        "term": "rock and roll",
        "country": "US",
        "media": "podcast",
        "entity": "podcast",
        "limit": "10",
        "lang": "en_us",
        "explicit": "Yes",
    }


@pytest.mark.asyncio
async def test_search_rejects_unusable_results_without_failing() -> None:
    response = search_response(
        raw_podcast(1),
        raw_podcast(2, kind="song"),
        # artistName missing: a podcast requires an author.
        raw_podcast(3, artistName=None),
        raw_podcast(4),
    )
    transport = httpx.MockTransport(lambda request: response)

    result = await ITunesProvider(transport=transport).search(ROCK_CRITERIA)

    assert [p.podcast_id for p in result.podcasts] == [1, 4]
    assert result.rejected == 2
    assert result.fetched == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="Internal Server Error"),
        httpx.Response(200, json={"unexpected": "payload"}),
    ],
)
async def test_search_raises_external_service_error(
    response: httpx.Response,
) -> None:
    transport = httpx.MockTransport(lambda request: response)

    with pytest.raises(ExternalServiceError):
        await ITunesProvider(transport=transport).search(ROCK_CRITERIA)


@pytest.mark.asyncio
async def test_search_uses_shared_client_and_keeps_it_open() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return search_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await ITunesProvider(client=client).search(ROCK_CRITERIA)

        assert not client.is_closed

    assert str(requests[0].url).startswith("https://itunes.apple.com/search?")
    assert requests[0].extensions["timeout"]["read"] == 10.0
