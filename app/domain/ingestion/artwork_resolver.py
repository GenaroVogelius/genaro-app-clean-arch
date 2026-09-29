from app.domain.ingestion.artwork_resolution import ArtworkResolution
from app.domain.ingestion.exceptions import ArtworkUnavailableError
from app.domain.interfaces.providers.artwork import ArtworkDownloaderInterface
from app.domain.interfaces.services import ColorPaletteExtractorInterface
from app.domain.interfaces.storage import ArtworkStorageInterface
from app.domain.podcast.aggregate import Podcast


class PodcastArtworkResolver:
    def __init__(
        self,
        downloader: ArtworkDownloaderInterface,
        storage: ArtworkStorageInterface,
        palette_extractor: ColorPaletteExtractorInterface,
    ):
        """
        Domain service that decides and processes the artwork of a podcast
        about to be stored.

        Args:
            downloader: Port used to download the artwork image.
            storage: Port used to store the artwork image.
            palette_extractor: Port used to extract the artwork's color palette.
        """
        self._downloader = downloader
        self._storage = storage
        self._palette_extractor = palette_extractor

    async def resolve(
        self, podcast: Podcast, stored: Podcast | None
    ) -> ArtworkResolution:
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
            The artwork to store (or None) and the reason it couldn't be
            processed (or None if there was no problem).
        """
        fetched = podcast.artwork
        previous = stored.artwork if stored is not None else None
        if fetched is None:
            return ArtworkResolution(artwork=previous, failure_reason="no artwork url")

        # An unprocessed previous artwork is superseded by the fetched one.
        if previous is not None and previous.path is None:
            previous = None
        if previous is not None and previous.source_url == fetched.source_url:
            return ArtworkResolution(artwork=previous)

        url = str(fetched.source_url)
        try:
            content = await self._downloader.download(url)
            # Extract before storing so an invalid image is never saved.
            palette = await self._palette_extractor.extract(content)
            path = await self._storage.store(podcast.podcast_id, content, url)
        except ArtworkUnavailableError as e:
            return ArtworkResolution(
                artwork=previous if previous is not None else fetched,
                failure_reason=str(e),
            )

        return ArtworkResolution(
            artwork=fetched.model_copy(update={"path": path, "palette": palette})
        )
