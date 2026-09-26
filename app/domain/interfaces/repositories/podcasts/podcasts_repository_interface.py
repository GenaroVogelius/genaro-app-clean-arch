from abc import ABC, abstractmethod

from app.domain.aggregates.podcast import Podcast
from app.domain.simple_entities.status import Status


class PodcastsReaderInterface(ABC):
    """
    Reader interface for the Podcast data
    """

    @abstractmethod
    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        """
        Get a stored podcast by its id.

        Args:
            podcast_id: id of the podcast in the source it was fetched from.

        Returns:
            The stored podcast, or None if it isn't stored.
        """


class PodcastsWriterInterface(ABC):
    """
    Writer interface for the Podcast data
    """

    @abstractmethod
    async def store_podcast(self, podcast: Podcast) -> Status:
        """
        Store a single podcast, inserting it or updating the stored one.

        Args:
            podcast: The podcast to store.

        Returns:
            Status CREATED if it was inserted, UPDATED if a stored podcast with the
            same id was changed, UNCHANGED if the stored one already had the same
            data, or ERROR if the podcast could not be stored.
        """


class PodcastsRepositoryInterface(PodcastsReaderInterface, PodcastsWriterInterface):
    pass
