from abc import ABC, abstractmethod

from app.domain.aggregates.podcast import Podcast


class PodcastLookupProviderInterface(ABC):
    """
    Port for looking up a single podcast by its id
    """

    @abstractmethod
    async def lookup_by_id(self, podcast_id: int) -> Podcast | None:
        """
        Look up a podcast by its id.

        Args:
            podcast_id: id of the podcast in the provider's source.

        Returns:
            The matching podcast, or None if the source has nothing for that id.

        Raises:
            NotAPodcastError: If the id refers to something other than a podcast.
            ExternalServiceError: If the source fails or returns an unusable payload.
        """
