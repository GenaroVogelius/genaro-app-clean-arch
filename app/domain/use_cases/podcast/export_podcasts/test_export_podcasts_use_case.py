import pytest

from app.domain.interfaces.repositories.podcasts import PodcastsExporterInterface
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.exceptions import PodcastRetrievalError
from app.domain.use_cases.podcast.export_podcasts.export_podcasts_use_case import (
    ExportPodcastsUseCase,
)


class FakePodcastsExporter(PodcastsExporterInterface):
    """In-memory keyset pagination over the given podcasts, sorted by id."""

    def __init__(self, podcasts: list[Podcast], error: Exception | None = None):
        self._podcasts = sorted(podcasts, key=lambda p: p.podcast_id)
        self._error = error
        self.calls: list[tuple[int | None, int]] = []

    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        self.calls.append((after_id, limit))
        if self._error is not None:
            raise self._error
        remaining = [
            p for p in self._podcasts if after_id is None or p.podcast_id > after_id
        ]
        return remaining[:limit]


def podcasts(count: int) -> list[Podcast]:
    """Build podcasts with ids 1..count."""
    return [
        Podcast(podcast_id=podcast_id, name=f"Show {podcast_id}", author="Someone")
        for podcast_id in range(1, count + 1)
    ]


async def export(use_case: ExportPodcastsUseCase) -> list[list[int]]:
    """Run the export and collect the ids of every batch."""
    return [[p.podcast_id for p in batch] async for batch in use_case.execute()]


@pytest.mark.asyncio
async def test_export_yields_nothing_for_an_empty_catalog() -> None:
    repository = FakePodcastsExporter([])
    use_case = ExportPodcastsUseCase(repository=repository, batch_size=2)

    assert await export(use_case) == []
    assert repository.calls == [(None, 2)]


@pytest.mark.asyncio
async def test_export_reads_batches_after_the_last_id() -> None:
    repository = FakePodcastsExporter(podcasts(5))
    use_case = ExportPodcastsUseCase(repository=repository, batch_size=2)

    assert await export(use_case) == [[1, 2], [3, 4], [5]]
    assert repository.calls == [(None, 2), (2, 2), (4, 2)]


@pytest.mark.asyncio
async def test_export_stops_on_empty_batch_when_catalog_fills_last_batch() -> None:
    repository = FakePodcastsExporter(podcasts(4))
    use_case = ExportPodcastsUseCase(repository=repository, batch_size=2)

    assert await export(use_case) == [[1, 2], [3, 4]]
    assert repository.calls == [(None, 2), (2, 2), (4, 2)]


@pytest.mark.asyncio
async def test_export_propagates_retrieval_errors() -> None:
    repository = FakePodcastsExporter([], error=PodcastRetrievalError("db down"))
    use_case = ExportPodcastsUseCase(repository=repository)

    with pytest.raises(PodcastRetrievalError):
        await export(use_case)
