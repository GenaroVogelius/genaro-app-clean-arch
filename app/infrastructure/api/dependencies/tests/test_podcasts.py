from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.settings import get_settings
from app.domain.common import Status, StatusType
from app.domain.ingestion import PodcastArtworkResolver
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.podcasts import PodcastSearchProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.queries import (
    PodcastListCriteria,
    PodcastPage,
    PodcastSearchCriteria,
    PodcastSearchResult,
)
from app.infrastructure.api.dependencies import podcasts
from app.infrastructure.providers.artwork_provider.http_artwork_downloader import (
    HttpArtworkDownloader,
)
from app.infrastructure.providers.itunes_provider.itunes_provider import ITunesProvider


class FakeSearchProvider(PodcastSearchProviderInterface):
    async def search(self, criteria: PodcastSearchCriteria) -> PodcastSearchResult:
        return PodcastSearchResult()


class FakeRepository(PodcastsRepositoryInterface):
    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        return None

    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        return PodcastPage(offset=criteria.offset, limit=criteria.limit)

    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        return []

    async def store_podcast(self, podcast: Podcast) -> Status:
        return Status(status=StatusType.CREATED)


class FakeLogger(LoggerInterface):
    def info(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def debug(self, message: str) -> None:
        pass

    def critical(self, message: str) -> None:
        pass


@pytest.fixture(autouse=True)
def clear_caches() -> Iterator[None]:
    """Reset the cached factories so every test builds fresh instances."""
    cached = (
        podcasts._get_itunes_provider,
        podcasts.get_podcasts_repository,
        podcasts.get_artwork_resolver,
    )
    for factory in cached:
        factory.cache_clear()
    yield
    for factory in cached:
        factory.cache_clear()


def downloader_client(resolver: PodcastArtworkResolver) -> object:
    """Get the HTTP client the resolver's artwork downloader sends with."""
    downloader = resolver._downloader
    assert isinstance(downloader, HttpArtworkDownloader)
    return downloader._client


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Open a client standing in for the one the app's lifespan shares."""
    async with httpx.AsyncClient() as client:
        yield client


async def test_lookup_and_search_providers_share_one_itunes_provider(
    http_client: httpx.AsyncClient,
) -> None:
    lookup = podcasts.get_lookup_provider(http_client)

    assert isinstance(lookup, ITunesProvider)
    assert lookup is podcasts.get_search_provider(http_client)
    assert lookup._client is http_client


async def test_itunes_provider_is_rebuilt_for_a_new_client(
    http_client: httpx.AsyncClient,
) -> None:
    first = podcasts.get_lookup_provider(http_client)

    async with httpx.AsyncClient() as new_client:
        assert podcasts.get_lookup_provider(new_client) is not first


async def test_artwork_resolver_is_built_once_per_client(
    http_client: httpx.AsyncClient,
) -> None:
    resolver = podcasts.get_artwork_resolver(http_client)

    assert resolver is podcasts.get_artwork_resolver(http_client)
    assert downloader_client(resolver) is http_client


async def test_ingest_podcasts_use_case_uses_configured_concurrency(
    http_client: httpx.AsyncClient,
) -> None:
    settings = get_settings().model_copy(update={"PODCAST_INGEST_CONCURRENCY": 7})

    use_case = podcasts.get_ingest_podcasts_use_case(
        provider=FakeSearchProvider(),
        repository=FakeRepository(),
        artwork_resolver=podcasts.get_artwork_resolver(http_client),
        logger=FakeLogger(),
        settings=settings,
    )

    assert use_case._max_concurrency == 7


def test_export_podcasts_use_case_uses_configured_batch_size() -> None:
    settings = get_settings().model_copy(update={"PODCAST_EXPORT_BATCH_SIZE": 250})
    repository = FakeRepository()

    use_case = podcasts.get_export_podcasts_use_case(
        repository=repository, settings=settings
    )

    assert use_case._batch_size == 250
    assert use_case._repository is repository


def test_routes_resolve_adapters_with_the_app_http_client() -> None:
    app = FastAPI()
    # Stand-in for the client the lifespan opens; never sends a request here.
    shared = object()
    app.state.http_client = shared

    @app.get("/wiring")
    async def wiring(
        lookup: podcasts.LookupProviderDep,
        resolver: podcasts.ArtworkResolverDep,
    ):
        assert isinstance(lookup, ITunesProvider)
        return {
            "lookup": lookup._client is shared,
            "downloader": downloader_client(resolver) is shared,
        }

    response = TestClient(app).get("/wiring")

    assert response.json() == {"lookup": True, "downloader": True}
