from abc import ABC, abstractmethod

from app.domain.common import Status
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.queries import PodcastListCriteria, PodcastPage


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


class PodcastsListerInterface(ABC):
    """
    Lister interface for the Podcast data
    """

    @abstractmethod
    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        """
        List a page of stored podcasts, sorted by name and then by id.

        Args:
            criteria: Text matched case-insensitively as a substring of the name
                or the author (every podcast when None), plus the offset and
                limit of the page.

        Returns:
            The podcasts of the requested page, and the total number of podcasts
            matching the criteria before pagination.
        """


class PodcastsExporterInterface(ABC):
    """
    Exporter interface for the Podcast data, reading every stored podcast a
    batch at a time
    """

    @abstractmethod
    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        """
        List the next batch of stored podcasts, sorted by id (keyset pagination).

        Args:
            after_id: Only podcasts with a greater id are listed. None starts
                from the first podcast.
            limit: Maximum number of podcasts to return.

        Returns:
            Up to limit podcasts with an id greater than after_id, sorted by id.
            Empty once there are no more podcasts.

        Raises:
            PodcastRetrievalError: The stored podcasts could not be read.
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


class PodcastsRepositoryInterface(
    PodcastsReaderInterface,
    PodcastsListerInterface,
    PodcastsExporterInterface,
    PodcastsWriterInterface,
):
    pass
