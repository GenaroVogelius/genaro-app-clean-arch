import pytest

from app.domain.interfaces.repositories.podcasts import PodcastsReaderInterface
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.exceptions import PodcastNotFoundError
from app.domain.use_cases.podcast.get_podcast.get_podcast_use_case import (
    GetPodcastUseCase,
)


class FakePodcastsReader(PodcastsReaderInterface):
    def __init__(self, stored: Podcast | None = None):
        self._stored = stored
        self.get_calls: list[int] = []

    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        self.get_calls.append(podcast_id)
        return self._stored


def podcast() -> Podcast:
    """Build a podcast resembling The Daily."""
    return Podcast.model_validate(
        {
            "podcast_id": 1200361736,
            "name": "The Daily",
            "author": "The New York Times",
            "feed_url": "https://feeds.simplecast.com/Sl5CSM3S",
        }
    )


@pytest.mark.asyncio
async def test_get_podcast_returns_stored_podcast() -> None:
    repository = FakePodcastsReader(stored=podcast())
    use_case = GetPodcastUseCase(repository=repository)

    assert await use_case.execute(1200361736) == podcast()
    assert repository.get_calls == [1200361736]


@pytest.mark.asyncio
async def test_get_podcast_raises_not_found_when_missing() -> None:
    use_case = GetPodcastUseCase(repository=FakePodcastsReader(stored=None))

    with pytest.raises(PodcastNotFoundError):
        await use_case.execute(1)
