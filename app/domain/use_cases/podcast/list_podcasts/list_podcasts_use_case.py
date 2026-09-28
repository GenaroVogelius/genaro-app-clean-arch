from app.domain.interfaces.repositories.podcasts import PodcastsListerInterface
from app.domain.simple_entities.podcast_list_criteria import PodcastListCriteria
from app.domain.simple_entities.podcast_page import PodcastPage


class ListPodcastsUseCase:
    def __init__(self, repository: PodcastsListerInterface):
        """
        Use case for listing stored podcasts, a page at a time.
        Args:
            repository: Port used to list the stored podcasts.
        """
        self._repository = repository

    async def execute(self, criteria: PodcastListCriteria) -> PodcastPage:
        """
        List a page of stored podcasts, optionally searching by name or author.

        Args:
            criteria: Search text, offset and limit of the page.

        Returns:
            The podcasts of the page and how many podcasts matched in total.
        """
        return await self._repository.list_podcasts(criteria)
