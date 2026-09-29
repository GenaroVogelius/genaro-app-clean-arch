from abc import ABC, abstractmethod

from app.domain.podcast.queries import PodcastSearchCriteria, PodcastSearchResult


class PodcastSearchProviderInterface(ABC):
    """
    Port for searching a batch of podcasts
    """

    @abstractmethod
    async def search(self, criteria: PodcastSearchCriteria) -> PodcastSearchResult:
        """
        Search podcasts matching the criteria.

        Results that can't be turned into a podcast are left out and counted in
        the result's `rejected`, so a single bad result never fails the search.

        Args:
            criteria: What to search for.

        Returns:
            The matching podcasts and how many results were rejected.

        Raises:
            ExternalServiceError: If the source fails or returns an unusable payload.
        """
