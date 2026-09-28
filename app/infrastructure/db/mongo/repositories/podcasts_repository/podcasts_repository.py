import re
from typing import Any

from app.domain.aggregates.podcast import Podcast
from app.domain.exceptions import PodcastRetrievalError
from app.domain.interfaces.mapper import MapperInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.simple_entities.podcast_list_criteria import PodcastListCriteria
from app.domain.simple_entities.podcast_page import PodcastPage
from app.domain.simple_entities.status import Status, StatusType
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_document import (  # noqa: E501
    PodcastDocument,
)
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_mapper import (  # noqa: E501
    PodcastMapper,
)
from app.infrastructure.logger import logger


class MongoPodcastsRepository(PodcastsRepositoryInterface):
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

    async def list_podcasts(self, criteria: PodcastListCriteria) -> PodcastPage:
        """
        List a page of stored podcasts, sorted by name and then by podcast_id.

        Args:
            criteria: Text matched case-insensitively as a substring of the name
                or the author (every podcast when None), plus the offset and
                limit of the page.

        Returns:
            The podcasts of the requested page, and the total number of podcasts
            matching the criteria before pagination.
        """
        query = _search_filter(criteria.q)
        total = await PodcastDocument.find(query).count()
        documents = (
            await PodcastDocument.find(query)
            .sort("+name", "+podcast_id")
            .skip(criteria.offset)
            .limit(criteria.limit)
            .to_list()
        )
        return PodcastPage(
            items=[self._mapper.map(document, Podcast) for document in documents],
            total=total,
            offset=criteria.offset,
            limit=criteria.limit,
        )

    async def list_podcasts_after(
        self, after_id: int | None, limit: int
    ) -> list[Podcast]:
        """
        List the next batch of stored podcasts, sorted by podcast_id (keyset
        pagination on its unique index, so no cursor stays open between
        batches).

        Args:
            after_id: Only podcasts with a greater podcast_id are listed. None
                starts from the first podcast.
            limit: Maximum number of podcasts to return.

        Returns:
            Up to limit podcasts with a podcast_id greater than after_id,
            sorted by podcast_id.

        Raises:
            PodcastRetrievalError: The database query failed.
        """
        query: dict[str, Any] = (
            {} if after_id is None else {"podcast_id": {"$gt": after_id}}
        )
        try:
            documents = (
                await PodcastDocument.find(query)
                .sort("+podcast_id")
                .limit(limit)
                .to_list()
            )
        except Exception as e:
            logger.error(f"Error listing podcasts after id {after_id}: {e}")
            raise PodcastRetrievalError("stored podcasts could not be read") from e
        return [self._mapper.map(document, Podcast) for document in documents]

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


def _search_filter(q: str | None) -> dict[str, Any]:
    """
    Build the MongoDB filter matching podcasts whose name or author contains
    the search text, ignoring case.

    Args:
        q: The search text, matched literally, or None to match every podcast.

    Returns:
        The filter to query the podcasts collection with.
    """
    if q is None:
        return {}
    pattern = {"$regex": re.escape(q), "$options": "i"}
    return {"$or": [{"name": pattern}, {"author": pattern}]}
