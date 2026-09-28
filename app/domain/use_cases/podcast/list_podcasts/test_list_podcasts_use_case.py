import pytest

from app.domain.aggregates.podcast import Podcast
from app.domain.interfaces.repositories.podcasts import PodcastsListerInterface
from app.domain.simple_entities.podcast_list_criteria import PodcastListCriteria
from app.domain.simple_entities.podcast_page import PodcastPage
from app.domain.use_cases.podcast.list_podcasts.list_podcasts_use_case import (
    ListPodcastsUseCase,
)


class FakePodcastsLister(PodcastsListerInterface):
    def __init__(self, page: PodcastPage):
        self._page = page
        self.list_calls: list[PodcastListCriteria] = []

    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        self.list_calls.append(criteria)
        return self._page


def podcast() -> Podcast:
    """Build a podcast resembling The Daily."""
    return Podcast.model_validate(
        {
            "podcast_id": 1200361736,
            "name": "The Daily",
            "author": "The New York Times",
        }
    )


@pytest.mark.asyncio
async def test_list_podcasts_returns_page_from_repository() -> None:
    page = PodcastPage(items=[podcast()], total=41, offset=20, limit=20)
    repository = FakePodcastsLister(page)
    use_case = ListPodcastsUseCase(repository=repository)
    criteria = PodcastListCriteria(q="daily", offset=20, limit=20)

    assert await use_case.execute(criteria) == page
    assert repository.list_calls == [criteria]


def test_criteria_treats_blank_q_as_no_search() -> None:
    assert PodcastListCriteria(q="   ").q is None


def test_criteria_strips_q() -> None:
    assert PodcastListCriteria(q="  daily ").q == "daily"
