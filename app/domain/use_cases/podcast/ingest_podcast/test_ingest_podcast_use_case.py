import pytest

from app.domain.aggregates.podcast import Artwork, PaletteColor, Podcast
from app.domain.exceptions import (
    ArtworkUnavailableError,
    NotAPodcastError,
    PodcastNotFoundError,
    PodcastPersistenceError,
)
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.domain.interfaces.providers.podcasts import PodcastLookupProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.interfaces.services import ColorPaletteExtractorInterface
from app.domain.interfaces.storage import ArtworkStorageInterface
from app.domain.services.podcast_artwork import PodcastArtworkResolver
from app.domain.simple_entities.podcast_list_criteria import PodcastListCriteria
from app.domain.simple_entities.podcast_page import PodcastPage
from app.domain.simple_entities.status import Status, StatusType
from app.domain.use_cases.podcast.ingest_podcast.ingest_podcast_use_case import (
    IngestPodcastUseCase,
)

ARTWORK_URL = "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
IMAGE = b"image-bytes"
PALETTE = [PaletteColor(hex="#ff0000", proportion=0.75)]


class FakePodcastLookupProvider(PodcastLookupProviderInterface):
    def __init__(self, result: Podcast | None = None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.lookup_calls: list[int] = []

    async def lookup_by_id(self, podcast_id: int) -> Podcast | None:
        self.lookup_calls.append(podcast_id)
        if self._error is not None:
            raise self._error
        return self._result


class FakePodcastsRepository(PodcastsRepositoryInterface):
    def __init__(self, stored: Podcast | None = None, status: Status | None = None):
        self._stored = stored
        self._status = status or Status(status=StatusType.CREATED, message="stored")
        self.store_calls: list[Podcast] = []

    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        return self._stored

    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        return PodcastPage(offset=criteria.offset, limit=criteria.limit)

    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        return []

    async def store_podcast(self, podcast: Podcast) -> Status:
        self.store_calls.append(podcast)
        return self._status


class FakeArtworkDownloader(ArtworkDownloaderInterface):
    def __init__(self, error: Exception | None = None):
        self._error = error
        self.download_calls: list[str] = []

    async def download(self, url: str) -> bytes:
        self.download_calls.append(url)
        if self._error is not None:
            raise self._error
        return IMAGE


class FakeArtworkStorage(ArtworkStorageInterface):
    def __init__(self) -> None:
        self.store_calls: list[tuple[int, bytes, str]] = []

    async def store(self, podcast_id: int, content: bytes, source_url: str) -> str:
        self.store_calls.append((podcast_id, content, source_url))
        return f"media/artwork/{podcast_id}.jpg"


class FakeColorPaletteExtractor(ColorPaletteExtractorInterface):
    def __init__(self) -> None:
        self.extract_calls: list[bytes] = []

    async def extract(self, content: bytes) -> list[PaletteColor]:
        self.extract_calls.append(content)
        return PALETTE


class FakeLogger(LoggerInterface):
    def __init__(self) -> None:
        self.warning_messages: list[str] = []

    def info(self, message: str) -> None:
        raise NotImplementedError()

    def error(self, message: str) -> None:
        raise NotImplementedError()

    def warning(self, message: str) -> None:
        self.warning_messages.append(message)

    def debug(self, message: str) -> None:
        raise NotImplementedError()

    def critical(self, message: str) -> None:
        raise NotImplementedError()


class Harness:
    """Holds the fakes wired into a use case, so tests can inspect them."""

    def __init__(
        self,
        provider: FakePodcastLookupProvider,
        repository: FakePodcastsRepository | None = None,
        downloader: FakeArtworkDownloader | None = None,
    ):
        self.provider = provider
        self.repository = repository or FakePodcastsRepository()
        self.downloader = downloader or FakeArtworkDownloader()
        self.storage = FakeArtworkStorage()
        self.extractor = FakeColorPaletteExtractor()
        self.logger = FakeLogger()
        self.use_case = IngestPodcastUseCase(
            provider=self.provider,
            repository=self.repository,
            artwork_resolver=PodcastArtworkResolver(
                downloader=self.downloader,
                storage=self.storage,
                palette_extractor=self.extractor,
            ),
            logger=self.logger,
        )

    @property
    def stored_podcast(self) -> Podcast:
        """The single podcast handed to the repository."""
        assert len(self.repository.store_calls) == 1
        return self.repository.store_calls[0]


def podcast(artwork_url: str | None = ARTWORK_URL, **overrides) -> Podcast:
    """Build a minimal podcast whose artwork (if any) is unprocessed."""
    return Podcast.model_validate(
        {
            "podcast_id": 1200361736,
            "name": "The Daily",
            "author": "The New York Times",
            "artwork": None if artwork_url is None else unprocessed(artwork_url),
            **overrides,
        }
    )


def unprocessed(source_url: str = ARTWORK_URL) -> Artwork:
    """Build an artwork as the provider returns it: only its source URL."""
    return Artwork.model_validate({"source_url": source_url})


def artwork(source_url: str = ARTWORK_URL) -> Artwork:
    """Build a previously stored, processed artwork."""
    return Artwork.model_validate(
        {
            "source_url": source_url,
            "path": "media/artwork/old.jpg",
            "palette": [{"hex": "#00ff00", "proportion": 1.0}],
        }
    )


@pytest.mark.asyncio
async def test_ingest_podcast_processes_artwork_and_returns_status() -> None:
    stored = Status(status=StatusType.CREATED, message="inserted podcast 1200361736")
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(status=stored),
    )

    result = await harness.use_case.execute(1200361736)

    assert result == stored
    assert harness.provider.lookup_calls == [1200361736]
    assert harness.downloader.download_calls == [ARTWORK_URL]
    assert harness.extractor.extract_calls == [IMAGE]
    assert harness.storage.store_calls == [(1200361736, IMAGE, ARTWORK_URL)]
    assert harness.stored_podcast.artwork == Artwork.model_validate(
        {
            "source_url": ARTWORK_URL,
            "path": "media/artwork/1200361736.jpg",
            "palette": PALETTE,
        }
    )
    assert harness.logger.warning_messages == []


@pytest.mark.asyncio
async def test_ingest_podcast_without_artwork_url_skips_artwork() -> None:
    harness = Harness(FakePodcastLookupProvider(result=podcast(artwork_url=None)))

    result = await harness.use_case.execute(1200361736)

    assert result.status == StatusType.CREATED
    assert result.message == "stored (artwork unavailable: no artwork url)"
    assert harness.downloader.download_calls == []
    assert harness.stored_podcast.artwork is None
    assert len(harness.logger.warning_messages) == 1


@pytest.mark.asyncio
async def test_ingest_podcast_without_artwork_url_keeps_previous_artwork() -> None:
    previous = artwork()
    harness = Harness(
        FakePodcastLookupProvider(result=podcast(artwork_url=None)),
        FakePodcastsRepository(stored=podcast(artwork=previous)),
    )

    await harness.use_case.execute(1200361736)

    assert harness.stored_podcast.artwork == previous


@pytest.mark.asyncio
async def test_ingest_podcast_keeps_previous_artwork_when_download_fails() -> None:
    previous = artwork(source_url="https://example.com/old.jpg")
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(stored=podcast(artwork=previous)),
        FakeArtworkDownloader(error=ArtworkUnavailableError("download failed: 404")),
    )

    result = await harness.use_case.execute(1200361736)

    assert result.status == StatusType.CREATED
    assert result.message == "stored (artwork unavailable: download failed: 404)"
    assert harness.stored_podcast.artwork == previous
    assert harness.extractor.extract_calls == []
    assert harness.storage.store_calls == []
    assert "download failed: 404" in harness.logger.warning_messages[0]


@pytest.mark.asyncio
async def test_ingest_podcast_stores_unprocessed_artwork_when_download_fails() -> None:
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        downloader=FakeArtworkDownloader(
            error=ArtworkUnavailableError("download failed: 404")
        ),
    )

    result = await harness.use_case.execute(1200361736)

    assert result.message == "stored (artwork unavailable: download failed: 404)"
    assert harness.stored_podcast.artwork == unprocessed()
    assert harness.storage.store_calls == []


@pytest.mark.asyncio
async def test_ingest_podcast_retries_previously_unprocessed_artwork() -> None:
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(stored=podcast()),
    )

    await harness.use_case.execute(1200361736)

    assert harness.downloader.download_calls == [ARTWORK_URL]
    artwork_stored = harness.stored_podcast.artwork
    assert artwork_stored is not None
    assert artwork_stored.path == "media/artwork/1200361736.jpg"
    assert artwork_stored.palette == PALETTE


@pytest.mark.asyncio
async def test_ingest_podcast_reuses_artwork_when_url_is_unchanged() -> None:
    previous = artwork()
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(stored=podcast(artwork=previous)),
    )

    result = await harness.use_case.execute(1200361736)

    assert result.message == "stored"
    assert harness.downloader.download_calls == []
    assert harness.stored_podcast.artwork == previous


@pytest.mark.asyncio
async def test_ingest_podcast_downloads_artwork_again_when_url_changed() -> None:
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(
            stored=podcast(artwork=artwork(source_url="https://example.com/old.png"))
        ),
    )

    await harness.use_case.execute(1200361736)

    assert harness.downloader.download_calls == [ARTWORK_URL]
    artwork_stored = harness.stored_podcast.artwork
    assert artwork_stored is not None
    assert str(artwork_stored.source_url) == ARTWORK_URL
    assert artwork_stored.palette == PALETTE


@pytest.mark.asyncio
async def test_ingest_podcast_raises_when_not_found() -> None:
    harness = Harness(FakePodcastLookupProvider(result=None))

    with pytest.raises(PodcastNotFoundError):
        await harness.use_case.execute(1)

    assert harness.repository.store_calls == []
    assert harness.downloader.download_calls == []


@pytest.mark.asyncio
async def test_ingest_podcast_propagates_not_a_podcast_error() -> None:
    harness = Harness(FakePodcastLookupProvider(error=NotAPodcastError("a song")))

    with pytest.raises(NotAPodcastError):
        await harness.use_case.execute(1)

    assert harness.repository.store_calls == []


@pytest.mark.asyncio
async def test_ingest_podcast_raises_when_store_fails() -> None:
    harness = Harness(
        FakePodcastLookupProvider(result=podcast()),
        FakePodcastsRepository(
            status=Status(status=StatusType.ERROR, message="db down")
        ),
    )

    with pytest.raises(PodcastPersistenceError, match="db down"):
        await harness.use_case.execute(1200361736)

    assert len(harness.repository.store_calls) == 1
