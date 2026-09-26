from pathlib import PurePosixPath
from urllib.parse import urlparse

from app.domain.aggregates.podcast import Artwork, Podcast
from app.domain.exceptions import (
    ArtworkUnavailableError,
    PodcastNotFoundError,
    PodcastPersistenceError,
)
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.domain.interfaces.providers.podcasts import PodcastLookupProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.interfaces.services import ColorPaletteExtractorInterface
from app.domain.interfaces.storage import ArtworkStorageInterface
from app.domain.simple_entities.status import Status, StatusType

# Used when the artwork URL has no file extension.
DEFAULT_ARTWORK_EXTENSION = ".jpg"


class IngestPodcastUseCase:
    def __init__(
        self,
        provider: PodcastLookupProviderInterface,
        repository: PodcastsRepositoryInterface,
        downloader: ArtworkDownloaderInterface,
        storage: ArtworkStorageInterface,
        palette_extractor: ColorPaletteExtractorInterface,
        logger: LoggerInterface,
    ):
        """
        Use case for ingesting a SINGLE podcast by its id, together with its
        artwork image and color palette.
        Args:
            provider: Port used to look up the podcast.
            repository: Port used to read the stored podcast and store the new one.
            downloader: Port used to download the artwork image.
            storage: Port used to store the artwork image.
            palette_extractor: Port used to extract the artwork's color palette.
            logger: Port used to warn when the artwork can't be processed.
        """
        self._provider = provider
        self._repository = repository
        self._downloader = downloader
        self._storage = storage
        self._palette_extractor = palette_extractor
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
        artwork, artwork_issue = await self._resolve_artwork(podcast, stored)
        podcast = podcast.model_copy(update={"artwork": artwork})

        status = await self._repository.store_podcast(podcast)
        if status.status == StatusType.ERROR:
            raise PodcastPersistenceError(
                f"podcast {podcast_id} could not be stored: {status.message}"
            )

        if artwork_issue is not None:
            self._logger.warning(
                f"artwork unavailable for podcast {podcast_id}: {artwork_issue}"
            )
            message = f"{status.message or ''} (artwork unavailable: {artwork_issue})"
            status = status.model_copy(update={"message": message.strip()})

        return status

    async def _resolve_artwork(
        self, podcast: Podcast, stored: Podcast | None
    ) -> tuple[Artwork | None, str | None]:
        """
        Decide the artwork of the podcast to store.

        The provider only sets the artwork's source_url. The artwork is only
        downloaded when the stored one was never processed or its URL changed.
        When it can't be processed, the previously processed artwork is kept or,
        if there is none, the unprocessed one is stored so its URL isn't lost.

        Args:
            podcast: The podcast fetched from the provider.
            stored: The currently stored version of the podcast, if any.

        Returns:
            The artwork to store (or None), and the reason it couldn't be
            processed (or None if there was no problem).
        """
        fetched = podcast.artwork
        previous = stored.artwork if stored is not None else None
        if fetched is None:
            return previous, "no artwork url"

        # An unprocessed previous artwork is superseded by the fetched one.
        if previous is not None and previous.path is None:
            previous = None
        if previous is not None and previous.source_url == fetched.source_url:
            return previous, None

        url = str(fetched.source_url)
        try:
            content = await self._downloader.download(url)
            # Extract before storing so an invalid image is never saved.
            palette = await self._palette_extractor.extract(content)
            path = await self._storage.store(
                podcast.podcast_id, content, _extension_of(url)
            )
        except ArtworkUnavailableError as e:
            return (previous if previous is not None else fetched), str(e)

        return fetched.model_copy(update={"path": path, "palette": palette}), None


def _extension_of(url: str) -> str:
    """
    Get the file extension of the file a URL points to.

    Args:
        url: URL of the file.

    Returns:
        The lowercase extension including the dot, or DEFAULT_ARTWORK_EXTENSION
        if the URL has none.
    """
    suffix = PurePosixPath(urlparse(url).path).suffix.lower()
    return suffix or DEFAULT_ARTWORK_EXTENSION
