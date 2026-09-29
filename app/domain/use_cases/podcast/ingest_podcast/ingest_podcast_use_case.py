from app.domain.common import Status, StatusType
from app.domain.ingestion import PodcastArtworkResolver
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.podcasts import PodcastLookupProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.podcast.exceptions import PodcastNotFoundError, PodcastPersistenceError


class IngestPodcastUseCase:
    def __init__(
        self,
        provider: PodcastLookupProviderInterface,
        repository: PodcastsRepositoryInterface,
        artwork_resolver: PodcastArtworkResolver,
        logger: LoggerInterface,
    ):
        """
        Use case for ingesting a SINGLE podcast by its id, together with its
        artwork image and color palette.
        Args:
            provider: Port used to look up the podcast.
            repository: Port used to read the stored podcast and store the new one.
            artwork_resolver: Service that decides and processes the artwork.
            logger: Port used to warn when the artwork can't be processed.
        """
        self._provider = provider
        self._repository = repository
        self._artwork_resolver = artwork_resolver
        self._logger = logger

    async def execute(self, podcast_id: int) -> Status:
        """
        Fetch a single podcast by its id, process its artwork and store it.

        Artwork problems never fail the ingestion: the previously stored artwork
        (if any) is kept, a warning is logged and the returned status message
        says why the artwork is unavailable.

        Args:
            podcast_id: id of the podcast.

        Returns:
            The storage status: CREATED, UPDATED or UNCHANGED.

        Raises:
            PodcastNotFoundError: If the provider has nothing for that id.
            NotAPodcastError: If the id refers to something other than a podcast
                (raised by the provider).
            ExternalServiceError: If the provider fails (raised by the provider).
            PodcastPersistenceError: If the podcast could not be stored.
        """
        podcast = await self._provider.lookup_by_id(podcast_id)
        if podcast is None:
            raise PodcastNotFoundError(f"podcast {podcast_id} not found")

        stored = await self._repository.get_podcast_by_id(podcast_id)
        resolution = await self._artwork_resolver.resolve(podcast, stored)
        podcast = podcast.model_copy(update={"artwork": resolution.artwork})

        status = await self._repository.store_podcast(podcast)
        if status.status == StatusType.ERROR:
            raise PodcastPersistenceError(
                f"podcast {podcast_id} could not be stored: {status.message}"
            )

        failure_reason = resolution.failure_reason
        if failure_reason is not None:
            self._logger.warning(
                f"artwork unavailable for podcast {podcast_id}: {failure_reason}"
            )
            message = f"{status.message or ''} (artwork unavailable: {failure_reason})"
            status = status.model_copy(update={"message": message.strip()})

        return status
