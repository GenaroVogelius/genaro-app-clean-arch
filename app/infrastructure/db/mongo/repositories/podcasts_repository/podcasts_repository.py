from app.domain.aggregates.podcast import Podcast
from app.domain.interfaces.mapper import MapperInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.simple_entities.status import Status, StatusType
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_document import (  # noqa: E501
    PodcastDocument,
)
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_mapper import (  # noqa: E501
    PodcastMapper,
)
from app.infrastructure.logger import logger


class PodcastsRepository(PodcastsRepositoryInterface):
    def __init__(self, mapper: MapperInterface | None = None):
        """
        MongoDB implementation of the podcasts repository.

        Args:
            mapper: Maps between Podcast and PodcastDocument.
                Defaults to PodcastMapper.
        """
        self._mapper = mapper or PodcastMapper()

    async def get_podcast_by_id(self, podcast_id: int) -> Podcast | None:
        """
        Get a stored podcast by its id.

        Args:
            podcast_id: id of the podcast in the source it was fetched from.

        Returns:
            The stored podcast, or None if it isn't stored.
        """
        document = await PodcastDocument.find_one(
            PodcastDocument.podcast_id == podcast_id
        )
        if document is None:
            return None
        return self._mapper.map(document, Podcast)

    async def store_podcast(self, podcast: Podcast) -> Status:
        """
        Insert the podcast, or replace the stored one with the same podcast_id
        when its data changed.

        Args:
            podcast: The podcast to store.

        Returns:
            Status CREATED if it was inserted, UPDATED if the stored one was
            replaced, UNCHANGED if the stored one already had the same data, or
            ERROR if the database operation failed.
        """
        try:
            existing = await PodcastDocument.find_one(
                PodcastDocument.podcast_id == podcast.podcast_id
            )
            if existing is None:
                await self._mapper.map(podcast, PodcastDocument).insert()
                return Status(
                    status=StatusType.CREATED,
                    message=f"inserted podcast {podcast.podcast_id}",
                )

            if self._mapper.map(existing, Podcast) == podcast:
                return Status(
                    status=StatusType.UNCHANGED,
                    message=f"podcast {podcast.podcast_id} already up to date",
                )

            document = self._mapper.map(podcast, PodcastDocument)
            document.id = existing.id
            await document.replace()
        except Exception as e:
            logger.error(f"Error storing podcast {podcast.podcast_id}: {e}")
            return Status(status=StatusType.ERROR, message=str(e))
        return Status(
            status=StatusType.UPDATED, message=f"updated podcast {podcast.podcast_id}"
        )
