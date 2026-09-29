from app.domain.interfaces.repositories.podcasts import PodcastsReaderInterface
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.exceptions import PodcastNotFoundError


class GetPodcastUseCase:
    def __init__(self, repository: PodcastsReaderInterface):
        """
        Use case for getting a SINGLE stored podcast by its id.
        Args:
            repository: Port used to read the stored podcast.
        """
        self._repository = repository

    async def execute(self, podcast_id: int) -> Podcast:
        """
        Get a stored podcast by its id.

        Args:
            podcast_id: id of the podcast.

        Returns:
            The stored podcast.

        Raises:
            PodcastNotFoundError: If no podcast is stored with that id.
        """
        podcast = await self._repository.get_podcast_by_id(podcast_id)
        if podcast is None:
            raise PodcastNotFoundError(f"podcast {podcast_id} not found")
        return podcast
