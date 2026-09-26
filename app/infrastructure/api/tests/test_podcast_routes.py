from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.aggregates.podcast import Artwork, PaletteColor, Podcast
from app.domain.exceptions import (
    ArtworkUnavailableError,
    ExternalServiceError,
    NotAPodcastError,
)
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.domain.interfaces.providers.podcasts import PodcastLookupProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.interfaces.services import ColorPaletteExtractorInterface
from app.domain.interfaces.storage import ArtworkStorageInterface
from app.domain.simple_entities.status import Status, StatusType
from app.domain.use_cases.podcast.get_podcast.get_podcast_use_case import (
    GetPodcastUseCase,
)
from app.domain.use_cases.podcast.ingest_podcast.ingest_podcast_use_case import (
    IngestPodcastUseCase,
)
from app.infrastructure.api.podcast_routes import PodcastRoutes


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


class FakePodcastsRepository(PodcastsRepositoryInterface):
    def __init__(self, status: Status | None = None, stored: Podcast | None = None):
        self._status = status or Status(status=StatusType.CREATED)
        self._stored = stored

    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        return self._stored

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
    async def store(self, podcast_id: int, content: bytes, extension: str) -> str:
        return f"media/artwork/{podcast_id}{extension}"


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


def client_for(
    provider: PodcastLookupProviderInterface,
    repository: PodcastsRepositoryInterface | None = None,
    downloader: ArtworkDownloaderInterface | None = None,
) -> TestClient:
    """Build a test client for PodcastRoutes wired to the given fakes."""
    repository = repository or FakePodcastsRepository()
    ingest_use_case = IngestPodcastUseCase(
        provider=provider,
        repository=repository,
        downloader=downloader or FakeArtworkDownloader(),
        storage=FakeArtworkStorage(),
        palette_extractor=FakeColorPaletteExtractor(),
        logger=FakeLogger(),
    )
    routes = PodcastRoutes(
        ingest_podcast_use_case=ingest_use_case,
        get_podcast_use_case=GetPodcastUseCase(repository=repository),
    )
    app = FastAPI()
    app.include_router(routes.router)
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
