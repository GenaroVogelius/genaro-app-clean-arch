import asyncio

import pytest

from app.domain.common import ExternalServiceError, Status, StatusType
from app.domain.ingestion import IngestionSummary, PodcastArtworkResolver
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.domain.interfaces.providers.podcasts import PodcastSearchProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.interfaces.services import ColorPaletteExtractorInterface
from app.domain.interfaces.storage import ArtworkStorageInterface
from app.domain.podcast.aggregate import Artwork, PaletteColor, Podcast
from app.domain.podcast.queries import (
    PodcastListCriteria,
    PodcastPage,
    PodcastSearchCriteria,
    PodcastSearchResult,
)
from app.domain.use_cases.podcast.ingest_podcasts.ingest_podcasts_use_case import (
    IngestPodcastsUseCase,
)

ARTWORK_URL = "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
PALETTE = [PaletteColor(hex="#ff0000", proportion=0.75)]
CRITERIA = PodcastSearchCriteria(term="rock and roll", limit=50, country="US")


class FakePodcastSearchProvider(PodcastSearchProviderInterface):
    def __init__(
        self,
        podcasts: list[Podcast] | None = None,
        rejected: int = 0,
        error: Exception | None = None,
    ):
        self._result = PodcastSearchResult(podcasts=podcasts or [], rejected=rejected)
        self._error = error
        self.search_calls: list[PodcastSearchCriteria] = []

    async def search(self, criteria: PodcastSearchCriteria) -> PodcastSearchResult:
        self.search_calls.append(criteria)
        if self._error is not None:
            raise self._error
        return self._result


class FakePodcastsRepository(PodcastsRepositoryInterface):
    """
    In-memory repository that stores by podcast_id, so re-ingesting the same
    data reports UNCHANGED, like the real one.
    """

    def __init__(
        self,
        stored: list[Podcast] | None = None,
        failing_ids: set[int] | None = None,
        erroring_ids: set[int] | None = None,
        delay: float = 0,
    ):
        self.podcasts = {p.podcast_id: p for p in stored or []}
        # Ids whose read raises, and ids whose store returns ERROR.
        self._failing_ids = failing_ids or set()
        self._erroring_ids = erroring_ids or set()
        self._delay = delay
        self.store_calls: list[Podcast] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        if podcast_id in self._failing_ids:
            raise RuntimeError("database unavailable")
        return self.podcasts.get(podcast_id)

    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        return PodcastPage(offset=criteria.offset, limit=criteria.limit)

    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        return []

    async def store_podcast(self, podcast: Podcast) -> Status:
        self.store_calls.append(podcast)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(self._delay)
        self.in_flight -= 1

        if podcast.podcast_id in self._erroring_ids:
            return Status(status=StatusType.ERROR, message="write failed")
        previous = self.podcasts.get(podcast.podcast_id)
        self.podcasts[podcast.podcast_id] = podcast
        if previous is None:
            return Status(status=StatusType.CREATED)
        if previous == podcast:
            return Status(status=StatusType.UNCHANGED)
        return Status(status=StatusType.UPDATED)


class FakeArtworkDownloader(ArtworkDownloaderInterface):
    def __init__(self) -> None:
        self.download_calls: list[str] = []

    async def download(self, url: str) -> bytes:
        self.download_calls.append(url)
        return b"image-bytes"


class FakeArtworkStorage(ArtworkStorageInterface):
    async def store(self, podcast_id: int, content: bytes, source_url: str) -> str:
        return f"media/artwork/{podcast_id}.jpg"


class FakeColorPaletteExtractor(ColorPaletteExtractorInterface):
    async def extract(self, content: bytes) -> list[PaletteColor]:
        return PALETTE


class FakeLogger(LoggerInterface):
    def __init__(self) -> None:
        self.warning_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        raise NotImplementedError()

    def error(self, message: str) -> None:
        self.error_messages.append(message)

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
        provider: FakePodcastSearchProvider,
        repository: FakePodcastsRepository | None = None,
        max_concurrency: int = 5,
    ):
        self.provider = provider
        self.repository = repository or FakePodcastsRepository()
        self.downloader = FakeArtworkDownloader()
        self.logger = FakeLogger()
        self.use_case = IngestPodcastsUseCase(
            provider=self.provider,
            repository=self.repository,
            artwork_resolver=PodcastArtworkResolver(
                downloader=self.downloader,
                storage=FakeArtworkStorage(),
                palette_extractor=FakeColorPaletteExtractor(),
            ),
            logger=self.logger,
            max_concurrency=max_concurrency,
        )

    async def run(self) -> IngestionSummary:
        return await self.use_case.execute(CRITERIA)


def podcast(podcast_id: int, **overrides) -> Podcast:
    """Build a minimal podcast whose artwork is unprocessed."""
    return Podcast.model_validate(
        {
            "podcast_id": podcast_id,
            "name": f"Rock show {podcast_id}",
            "author": "Some Author",
            "artwork": {"source_url": ARTWORK_URL},
            **overrides,
        }
    )


@pytest.mark.asyncio
async def test_ingest_podcasts_stores_new_podcasts_with_processed_artwork() -> None:
    harness = Harness(FakePodcastSearchProvider([podcast(1), podcast(2)]))

    summary = await harness.run()

    assert harness.provider.search_calls == [CRITERIA]
    assert summary == IngestionSummary(fetched=2, created=2)
    assert summary.stored == 2
    assert summary.skipped == 0
    stored = harness.repository.podcasts[1]
    assert stored.artwork is not None
    assert stored.artwork.path == "media/artwork/1.jpg"
    assert stored.artwork.palette == PALETTE


@pytest.mark.asyncio
async def test_ingest_podcasts_is_idempotent_when_run_twice() -> None:
    repository = FakePodcastsRepository()
    provider = FakePodcastSearchProvider([podcast(1), podcast(2)])
    await Harness(provider, repository).run()

    harness = Harness(provider, repository)
    summary = await harness.run()

    assert summary == IngestionSummary(fetched=2, unchanged=2)
    assert summary.stored == 0
    assert summary.skipped == 2
    assert len(repository.podcasts) == 2
    # The processed artwork is carried forward instead of downloaded again.
    assert harness.downloader.download_calls == []


@pytest.mark.asyncio
async def test_ingest_podcasts_counts_updated_podcasts() -> None:
    repository = FakePodcastsRepository()
    await Harness(FakePodcastSearchProvider([podcast(1)]), repository).run()

    summary = await Harness(
        FakePodcastSearchProvider([podcast(1, episode_count=10)]), repository
    ).run()

    assert summary == IngestionSummary(fetched=1, updated=1)
    assert summary.stored == 1


@pytest.mark.asyncio
async def test_ingest_podcasts_stores_duplicates_within_the_batch_once() -> None:
    harness = Harness(
        FakePodcastSearchProvider([podcast(1), podcast(1, name="Repeated")])
    )

    summary = await harness.run()

    assert summary == IngestionSummary(fetched=2, created=1, duplicates=1)
    assert summary.skipped == 1
    assert [p.name for p in harness.repository.store_calls] == ["Rock show 1"]


@pytest.mark.asyncio
async def test_ingest_podcasts_counts_rejected_results_as_failed() -> None:
    harness = Harness(FakePodcastSearchProvider([podcast(1)], rejected=2))

    summary = await harness.run()

    assert summary == IngestionSummary(fetched=3, created=1, failed=2)


@pytest.mark.asyncio
async def test_ingest_podcasts_counts_store_errors_as_failed() -> None:
    harness = Harness(
        FakePodcastSearchProvider([podcast(1), podcast(2)]),
        FakePodcastsRepository(erroring_ids={2}),
    )

    summary = await harness.run()

    assert summary == IngestionSummary(fetched=2, created=1, failed=1)
    assert len(harness.logger.error_messages) == 1


@pytest.mark.asyncio
async def test_ingest_podcasts_keeps_going_when_one_podcast_raises() -> None:
    harness = Harness(
        FakePodcastSearchProvider([podcast(1), podcast(2), podcast(3)]),
        FakePodcastsRepository(failing_ids={2}),
    )

    summary = await harness.run()

    assert summary == IngestionSummary(fetched=3, created=2, failed=1)
    assert set(harness.repository.podcasts) == {1, 3}
    assert "podcast 2" in harness.logger.error_messages[0]


@pytest.mark.asyncio
async def test_ingest_podcasts_keeps_previous_processed_artwork() -> None:
    processed = Artwork.model_validate(
        {
            "source_url": ARTWORK_URL,
            "path": "media/artwork/old.jpg",
            "palette": [{"hex": "#00ff00", "proportion": 1.0}],
        }
    )
    stored = podcast(1).model_copy(update={"artwork": processed})
    harness = Harness(
        FakePodcastSearchProvider([podcast(1)]), FakePodcastsRepository([stored])
    )

    summary = await harness.run()

    assert summary == IngestionSummary(fetched=1, unchanged=1)
    assert harness.repository.podcasts[1].artwork == processed
    assert harness.downloader.download_calls == []


@pytest.mark.asyncio
async def test_ingest_podcasts_logs_missing_artwork_without_failing() -> None:
    harness = Harness(FakePodcastSearchProvider([podcast(1, artwork=None)]))

    summary = await harness.run()

    assert summary == IngestionSummary(fetched=1, created=1)
    assert harness.logger.warning_messages == [
        "artwork unavailable for podcast 1: no artwork url"
    ]


@pytest.mark.asyncio
async def test_ingest_podcasts_propagates_search_errors() -> None:
    harness = Harness(FakePodcastSearchProvider(error=ExternalServiceError("down")))

    with pytest.raises(ExternalServiceError):
        await harness.run()

    assert harness.repository.store_calls == []


@pytest.mark.asyncio
async def test_ingest_podcasts_returns_empty_summary_when_nothing_found() -> None:
    summary = await Harness(FakePodcastSearchProvider()).run()

    assert summary == IngestionSummary()


@pytest.mark.asyncio
async def test_ingest_podcasts_bounds_concurrency() -> None:
    harness = Harness(
        FakePodcastSearchProvider([podcast(i) for i in range(1, 11)]),
        FakePodcastsRepository(delay=0.01),
        max_concurrency=3,
    )

    summary = await harness.run()

    assert summary.created == 10
    assert harness.repository.max_in_flight == 3
