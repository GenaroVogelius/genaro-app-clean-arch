import csv
import io
import re
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.common import ExternalServiceError, Status, StatusType
from app.domain.ingestion import ArtworkUnavailableError, PodcastArtworkResolver
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.domain.interfaces.providers.podcasts import (
    PodcastLookupProviderInterface,
    PodcastSearchProviderInterface,
)
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.interfaces.services import ColorPaletteExtractorInterface
from app.domain.interfaces.storage import ArtworkStorageInterface
from app.domain.podcast.aggregate import Artwork, PaletteColor, Podcast
from app.domain.podcast.exceptions import (
    NotAPodcastError,
    PodcastNotFoundError,
    PodcastPersistenceError,
    PodcastRetrievalError,
)
from app.domain.podcast.queries import (
    PodcastListCriteria,
    PodcastPage,
    PodcastSearchCriteria,
    PodcastSearchResult,
)
from app.domain.use_cases.podcast.export_podcasts.export_podcasts_use_case import (
    ExportPodcastsUseCase,
)
from app.infrastructure.api.dependencies.common import get_api_key_auth, get_logger
from app.infrastructure.api.dependencies.podcasts import (
    HealthCheck,
    get_artwork_resolver,
    get_export_podcasts_use_case,
    get_health_check,
    get_ingest_podcast_use_case,
    get_ingest_podcasts_use_case,
    get_lookup_provider,
    get_podcast_use_case,
    get_podcasts_repository,
    get_search_provider,
)
from app.infrastructure.api.podcast_routes import router
from app.infrastructure.api.security import ApiKeyAuth

API_KEY = "secret-key"


class FakePodcastLookupProvider(PodcastLookupProviderInterface):
    def __init__(
        self,
        result: Podcast | None = None,
        error: Exception | None = None,
    ):
        self._result = result
        self._error = error

    async def lookup_by_id(self, podcast_id: int) -> Podcast | None:
        if self._error is not None:
            raise self._error
        return self._result


class FakePodcastSearchProvider(PodcastSearchProviderInterface):
    def __init__(
        self,
        result: PodcastSearchResult | None = None,
        error: Exception | None = None,
    ):
        self._result = result or PodcastSearchResult()
        self._error = error
        self.search_calls: list[PodcastSearchCriteria] = []

    async def search(self, criteria: PodcastSearchCriteria) -> PodcastSearchResult:
        self.search_calls.append(criteria)
        if self._error is not None:
            raise self._error
        return self._result


class FakePodcastsRepository(PodcastsRepositoryInterface):
    def __init__(
        self,
        status: Status | None = None,
        stored: Podcast | None = None,
        listed: list[Podcast] | None = None,
        total: int | None = None,
        export_error: Exception | None = None,
        export_error_after_calls: int = 0,
    ):
        self._status = status or Status(status=StatusType.CREATED)
        self._stored = stored
        self._listed = listed or []
        self._total = len(self._listed) if total is None else total
        # Raised by list_podcasts_after once it was called this many times.
        self._export_error = export_error
        self._export_error_after_calls = export_error_after_calls
        self.list_calls: list[PodcastListCriteria] = []
        self.export_calls: list[tuple[int | None, int]] = []

    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        return self._stored

    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        self.list_calls.append(criteria)
        return PodcastPage(
            items=self._listed,
            total=self._total,
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        if (
            self._export_error is not None
            and len(self.export_calls) >= self._export_error_after_calls
        ):
            raise self._export_error
        self.export_calls.append((after_id, limit))
        remaining = sorted(
            (p for p in self._listed if after_id is None or p.podcast_id > after_id),
            key=lambda p: p.podcast_id,
        )
        return remaining[:limit]

    async def store_podcast(self, podcast: Podcast) -> Status:
        return self._status


class FakeArtworkDownloader(ArtworkDownloaderInterface):
    def __init__(self, error: Exception | None = None):
        self._error = error

    async def download(self, url: str) -> bytes:
        if self._error is not None:
            raise self._error
        return b"image-bytes"


class FakeArtworkStorage(ArtworkStorageInterface):
    async def store(self, podcast_id: int, content: bytes, source_url: str) -> str:
        return f"media/artwork/{podcast_id}.jpg"


class FakeColorPaletteExtractor(ColorPaletteExtractorInterface):
    async def extract(self, content: bytes) -> list[PaletteColor]:
        return [PaletteColor(hex="#ff0000", proportion=1.0)]


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


async def healthy() -> bool:
    """Health check that always reports the backing store as reachable."""
    return True


async def unhealthy() -> bool:
    """Health check that always reports the backing store as unreachable."""
    return False


def client_for(
    provider: PodcastLookupProviderInterface,
    repository: PodcastsRepositoryInterface | None = None,
    downloader: ArtworkDownloaderInterface | None = None,
    search_provider: PodcastSearchProviderInterface | None = None,
    health_check: HealthCheck | None = None,
    auth: ApiKeyAuth | None = None,
) -> TestClient:
    """
    Build a test client for the podcast routes whose leaf dependencies are
    overridden with the given fakes, with authentication disabled unless an
    auth is given. The real use cases are built around the fakes.
    """
    repository = repository or FakePodcastsRepository()
    search_provider = search_provider or FakePodcastSearchProvider()
    artwork_resolver = PodcastArtworkResolver(
        downloader=downloader or FakeArtworkDownloader(),
        storage=FakeArtworkStorage(),
        palette_extractor=FakeColorPaletteExtractor(),
    )
    auth = auth or ApiKeyAuth(enabled=False, api_key=None, logger=FakeLogger())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides.update(
        {
            get_lookup_provider: lambda: provider,
            get_search_provider: lambda: search_provider,
            get_podcasts_repository: lambda: repository,
            get_artwork_resolver: lambda: artwork_resolver,
            get_logger: FakeLogger,
            get_health_check: lambda: health_check or healthy,
            get_api_key_auth: lambda: auth,
        }
    )
    return TestClient(app)


def get_client_for(stored: Podcast | None) -> TestClient:
    """Build a test client whose repository has the given podcast stored."""
    return client_for(
        FakePodcastLookupProvider(), FakePodcastsRepository(stored=stored)
    )


def podcast() -> Podcast:
    """Build a podcast resembling The Daily, with its artwork unprocessed."""
    return Podcast.model_validate(
        {
            "podcast_id": 1200361736,
            "name": "The Daily",
            "author": "The New York Times",
            "feed_url": "https://feeds.simplecast.com/Sl5CSM3S",
            "episode_count": 2730,
            "artwork": {
                "source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
            },
        }
    )


def test_ingest_podcast_returns_201_when_created() -> None:
    client = client_for(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(
            Status(status=StatusType.CREATED, message="inserted podcast 1200361736")
        ),
    )

    response = client.post("/podcasts/1200361736/ingest")

    assert response.status_code == 201
    assert response.json() == {
        "status": "created",
        "message": "inserted podcast 1200361736",
    }


def test_ingest_podcast_returns_200_when_updated() -> None:
    client = client_for(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(Status(status=StatusType.UPDATED)),
    )

    response = client.post("/podcasts/1200361736/ingest")

    assert response.status_code == 200
    assert response.json()["status"] == "updated"


def test_ingest_podcast_returns_200_when_unchanged() -> None:
    client = client_for(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(Status(status=StatusType.UNCHANGED)),
    )

    response = client.post("/podcasts/1200361736/ingest")

    assert response.status_code == 200
    assert response.json()["status"] == "unchanged"


def test_ingest_podcast_returns_404_when_not_found() -> None:
    client = client_for(FakePodcastLookupProvider(result=None))

    assert client.post("/podcasts/1/ingest").status_code == 404


def test_ingest_podcast_returns_422_when_not_a_podcast() -> None:
    client = client_for(FakePodcastLookupProvider(error=NotAPodcastError("a song")))

    assert client.post("/podcasts/1/ingest").status_code == 422


def test_ingest_podcast_returns_502_when_provider_fails() -> None:
    client = client_for(
        FakePodcastLookupProvider(error=ExternalServiceError("source down"))
    )

    assert client.post("/podcasts/1/ingest").status_code == 502


def test_ingest_podcast_returns_503_when_store_fails() -> None:
    client = client_for(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(Status(status=StatusType.ERROR, message="db down")),
    )

    assert client.post("/podcasts/1/ingest").status_code == 503


def test_ingest_podcast_still_succeeds_when_artwork_fails() -> None:
    client = client_for(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(
            Status(status=StatusType.CREATED, message="inserted podcast 1200361736")
        ),
        FakeArtworkDownloader(error=ArtworkUnavailableError("download failed: 404")),
    )

    response = client.post("/podcasts/1200361736/ingest")

    assert response.status_code == 201
    assert response.json() == {
        "status": "created",
        "message": "inserted podcast 1200361736 "
        "(artwork unavailable: download failed: 404)",
    }


def test_get_podcast_returns_200_with_stored_podcast() -> None:
    artwork = Artwork.model_validate(
        {
            "source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
            "path": "media/artwork/1200361736.jpg",
            "palette": [{"hex": "#ff0000", "proportion": 0.75}],
        }
    )
    client = get_client_for(podcast().model_copy(update={"artwork": artwork}))

    response = client.get("/podcasts/1200361736")

    assert response.status_code == 200
    assert response.json() == {
        "podcast_id": 1200361736,
        "name": "The Daily",
        "author": "The New York Times",
        "feed_url": "https://feeds.simplecast.com/Sl5CSM3S",
        "view_url": None,
        "genre": None,
        "episode_count": 2730,
        "release_date": None,
        "country": None,
        "explicitness": None,
        "artwork": {
            "source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
            "path": "media/artwork/1200361736.jpg",
            "palette": [{"hex": "#ff0000", "proportion": 0.75}],
        },
    }


def test_get_podcast_returns_unprocessed_artwork() -> None:
    client = get_client_for(podcast())

    response = client.get("/podcasts/1200361736")

    assert response.status_code == 200
    assert response.json()["artwork"] == {
        "source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
        "path": None,
        "palette": [],
    }


def test_get_podcast_returns_null_artwork_when_it_has_none() -> None:
    client = get_client_for(podcast().model_copy(update={"artwork": None}))

    response = client.get("/podcasts/1200361736")

    assert response.status_code == 200
    assert response.json()["artwork"] is None


def test_get_podcast_returns_404_when_not_stored() -> None:
    client = get_client_for(None)

    assert client.get("/podcasts/1").status_code == 404


def test_get_podcast_returns_422_for_invalid_id() -> None:
    client = get_client_for(podcast())

    assert client.get("/podcasts/0").status_code == 422


def list_client_for(repository: FakePodcastsRepository) -> TestClient:
    """Build a test client whose listing reads from the given fake."""
    return client_for(FakePodcastLookupProvider(), repository)


def test_list_podcasts_returns_200_with_page() -> None:
    repository = FakePodcastsRepository(listed=[podcast()], total=41)

    response = list_client_for(repository).get(
        "/podcasts", params={"offset": 20, "limit": 20}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 41
    assert body["offset"] == 20
    assert body["limit"] == 20
    assert [item["podcast_id"] for item in body["items"]] == [1200361736]
    assert body["items"][0]["name"] == "The Daily"


def test_list_podcasts_returns_empty_page_when_nothing_matches() -> None:
    response = list_client_for(FakePodcastsRepository()).get("/podcasts")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "offset": 0, "limit": 20}


def test_list_podcasts_uses_default_criteria() -> None:
    repository = FakePodcastsRepository()

    list_client_for(repository).get("/podcasts")

    assert repository.list_calls == [PodcastListCriteria(q=None, offset=0, limit=20)]


def test_list_podcasts_forwards_query_params() -> None:
    repository = FakePodcastsRepository()

    response = list_client_for(repository).get(
        "/podcasts", params={"q": "daily", "offset": 40, "limit": 100}
    )

    assert response.status_code == 200
    assert repository.list_calls == [
        PodcastListCriteria(q="daily", offset=40, limit=100)
    ]


def test_list_podcasts_treats_blank_q_as_no_search() -> None:
    repository = FakePodcastsRepository()

    list_client_for(repository).get("/podcasts", params={"q": "   "})

    assert repository.list_calls[0].q is None


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"q": "x" * 201}],
)
def test_list_podcasts_returns_422_for_invalid_params(params: dict) -> None:
    repository = FakePodcastsRepository()

    response = list_client_for(repository).get("/podcasts", params=params)

    assert response.status_code == 422
    assert repository.list_calls == []


def export_client_for(
    repository: FakePodcastsRepository, batch_size: int = 2
) -> TestClient:
    """Build a test client whose export reads batches of batch_size from the fake."""
    client = client_for(FakePodcastLookupProvider(), repository)
    use_case = ExportPodcastsUseCase(repository=repository, batch_size=batch_size)
    assert isinstance(client.app, FastAPI)
    client.app.dependency_overrides[get_export_podcasts_use_case] = lambda: use_case
    return client


def minimal_podcast(podcast_id: int) -> Podcast:
    """Build a podcast with only the required fields set."""
    return Podcast(podcast_id=podcast_id, name=f"Show {podcast_id}", author="X")


def csv_rows(text: str) -> list[list[str]]:
    """Parse a CSV body into its rows."""
    return list(csv.reader(io.StringIO(text)))


def test_export_podcasts_streams_every_podcast_as_csv() -> None:
    repository = FakePodcastsRepository(
        listed=[minimal_podcast(i) for i in (3, 1, 5, 2, 4)]
    )

    response = export_client_for(repository).get("/podcasts/export")

    assert response.status_code == 200
    rows = csv_rows(response.text)
    assert rows[0][:3] == ["podcast_id", "name", "author"]
    assert [row[0] for row in rows[1:]] == ["1", "2", "3", "4", "5"]
    assert repository.export_calls == [(None, 2), (2, 2), (4, 2)]


def test_export_podcasts_flattens_the_podcast_fields() -> None:
    response = export_client_for(FakePodcastsRepository(listed=[podcast()])).get(
        "/podcasts/export"
    )

    header, row = csv_rows(response.text)
    exported = dict(zip(header, row, strict=True))
    assert exported["podcast_id"] == "1200361736"
    assert exported["name"] == "The Daily"
    assert exported["episode_count"] == "2730"
    assert exported["genre"] == ""
    assert exported["artwork_source_url"] == (
        "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
    )


def test_export_podcasts_is_a_csv_attachment() -> None:
    response = export_client_for(FakePodcastsRepository()).get("/podcasts/export")

    assert response.headers["content-type"].startswith("text/csv")
    assert re.fullmatch(
        r'attachment; filename="podcasts-\d{8}T\d{6}Z\.csv"',
        response.headers["content-disposition"],
    )


def test_export_podcasts_returns_only_header_when_nothing_is_stored() -> None:
    response = export_client_for(FakePodcastsRepository()).get("/podcasts/export")

    assert response.status_code == 200
    assert len(csv_rows(response.text)) == 1


def test_export_podcasts_uses_the_default_use_case_wiring() -> None:
    repository = FakePodcastsRepository(listed=[minimal_podcast(1)])

    response = client_for(FakePodcastLookupProvider(), repository).get(
        "/podcasts/export"
    )

    assert response.status_code == 200
    assert [row[0] for row in csv_rows(response.text)[1:]] == ["1"]


def test_export_podcasts_returns_503_when_first_batch_fails() -> None:
    repository = FakePodcastsRepository(
        listed=[minimal_podcast(1)],
        export_error=PodcastRetrievalError("db down"),
    )

    response = export_client_for(repository).get("/podcasts/export")

    assert response.status_code == 503
    assert response.json()["detail"] == "db down"


def test_export_podcasts_aborts_when_a_later_batch_fails() -> None:
    repository = FakePodcastsRepository(
        listed=[minimal_podcast(i) for i in range(1, 6)],
        export_error=PodcastRetrievalError("db down"),
        export_error_after_calls=1,
    )

    # The 200 is already sent, so the server can only abort the response;
    # TestClient surfaces that as the raised error.
    with pytest.raises(PodcastRetrievalError):
        export_client_for(repository).get("/podcasts/export")


def ingest_many_client_for(
    search_provider: FakePodcastSearchProvider,
    repository: FakePodcastsRepository | None = None,
) -> TestClient:
    """Build a test client whose bulk ingestion searches with the given fake."""
    return client_for(
        FakePodcastLookupProvider(),
        repository=repository,
        search_provider=search_provider,
    )


def test_ingest_podcasts_returns_200_with_summary() -> None:
    other = podcast().model_copy(update={"podcast_id": 2})
    search_provider = FakePodcastSearchProvider(
        PodcastSearchResult(podcasts=[podcast(), other, podcast()], rejected=1)
    )
    client = ingest_many_client_for(search_provider)

    response = client.post("/podcasts/ingest")

    assert response.status_code == 200
    assert response.json() == {
        "fetched": 4,
        "stored": 2,
        "skipped": 1,
        "failed": 1,
        "created": 2,
        "updated": 0,
        "unchanged": 0,
        "duplicates": 1,
    }


def test_ingest_podcasts_searches_rock_and_roll_by_default() -> None:
    search_provider = FakePodcastSearchProvider()

    ingest_many_client_for(search_provider).post("/podcasts/ingest")

    assert search_provider.search_calls == [
        PodcastSearchCriteria(term="rock and roll", limit=50, country="US")
    ]


def test_ingest_podcasts_forwards_query_params() -> None:
    search_provider = FakePodcastSearchProvider()

    response = ingest_many_client_for(search_provider).post(
        "/podcasts/ingest",
        params={"term": "punk rock", "limit": 200, "country": "GB"},
    )

    assert response.status_code == 200
    assert search_provider.search_calls == [
        PodcastSearchCriteria(term="punk rock", limit=200, country="GB")
    ]


def test_ingest_podcasts_reports_unchanged_when_nothing_changed() -> None:
    search_provider = FakePodcastSearchProvider(
        PodcastSearchResult(podcasts=[podcast()])
    )
    repository = FakePodcastsRepository(status=Status(status=StatusType.UNCHANGED))

    response = ingest_many_client_for(search_provider, repository).post(
        "/podcasts/ingest"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stored"] == 0
    assert body["skipped"] == 1
    assert body["unchanged"] == 1


def test_ingest_podcasts_returns_502_when_search_fails() -> None:
    search_provider = FakePodcastSearchProvider(
        error=ExternalServiceError("iTunes request /search failed")
    )

    response = ingest_many_client_for(search_provider).post("/podcasts/ingest")

    assert response.status_code == 502


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 201}, {"country": "usa"}, {"term": ""}],
)
def test_ingest_podcasts_returns_422_for_invalid_params(params: dict) -> None:
    search_provider = FakePodcastSearchProvider()

    response = ingest_many_client_for(search_provider).post(
        "/podcasts/ingest", params=params
    )

    assert response.status_code == 422
    assert search_provider.search_calls == []


def test_health_returns_200_when_store_is_reachable() -> None:
    client = client_for(FakePodcastLookupProvider(), health_check=healthy)

    response = client.get("/podcasts/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_store_is_unreachable() -> None:
    client = client_for(FakePodcastLookupProvider(), health_check=unhealthy)

    response = client.get("/podcasts/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def auth_client_for(stored: Podcast | None = None) -> TestClient:
    """Build a test client whose routes require API_KEY."""
    return client_for(
        FakePodcastLookupProvider(),
        FakePodcastsRepository(stored=stored),
        auth=ApiKeyAuth(enabled=True, api_key=API_KEY, logger=FakeLogger()),
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/podcasts"),
        ("GET", "/podcasts/1"),
        ("GET", "/podcasts/export"),
        ("POST", "/podcasts/1/ingest"),
        ("POST", "/podcasts/ingest"),
    ],
)
def test_protected_routes_return_401_without_api_key(method: str, path: str) -> None:
    client = auth_client_for(podcast())

    assert client.request(method, path).status_code == 401


def test_get_podcast_returns_200_with_valid_api_key() -> None:
    client = auth_client_for(podcast())

    response = client.get("/podcasts/1", headers={"X-API-Key": API_KEY})

    assert response.status_code == 200


def test_health_does_not_require_api_key() -> None:
    client = auth_client_for()

    assert client.get("/podcasts/health").status_code == 200


class FakeFailingUseCase:
    """Use case whose execution always raises the given error."""

    def __init__(self, error: Exception):
        self._error = error

    async def execute(self, *args: object) -> None:
        """Raise the error the fake was built with."""
        raise self._error


def use_case_client_for(
    dependency: Callable[..., object], use_case: object
) -> TestClient:
    """
    Build a test client whose given use case dependency is overridden with a
    fake use case, with authentication disabled.
    """
    app = FastAPI()
    app.include_router(router)
    auth = ApiKeyAuth(enabled=False, api_key=None, logger=FakeLogger())
    app.dependency_overrides.update(
        {dependency: lambda: use_case, get_api_key_auth: lambda: auth}
    )
    return TestClient(app)


def test_ingest_podcast_maps_persistence_error_to_503() -> None:
    client = use_case_client_for(
        get_ingest_podcast_use_case,
        FakeFailingUseCase(PodcastPersistenceError("db down")),
    )

    response = client.post("/podcasts/1/ingest")

    assert response.status_code == 503
    assert response.json()["detail"] == "db down"


def test_get_podcast_maps_not_found_error_to_404() -> None:
    client = use_case_client_for(
        get_podcast_use_case, FakeFailingUseCase(PodcastNotFoundError("missing"))
    )

    assert client.get("/podcasts/1").status_code == 404


def test_ingest_podcasts_maps_external_service_error_to_502() -> None:
    client = use_case_client_for(
        get_ingest_podcasts_use_case,
        FakeFailingUseCase(ExternalServiceError("iTunes down")),
    )

    assert client.post("/podcasts/ingest").status_code == 502
