import asyncio
from collections import Counter

from app.domain.aggregates.podcast import Podcast
from app.domain.interfaces.logger import LoggerInterface
from app.domain.interfaces.providers.podcasts import PodcastSearchProviderInterface
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.services.podcast_artwork import PodcastArtworkResolver
from app.domain.simple_entities.ingestion_summary import IngestionSummary
from app.domain.simple_entities.podcast_search_criteria import PodcastSearchCriteria
from app.domain.simple_entities.status import Status, StatusType

DEFAULT_MAX_CONCURRENCY = 5


class IngestPodcastsUseCase:
    def __init__(
        self,
        provider: PodcastSearchProviderInterface,
        repository: PodcastsRepositoryInterface,
        artwork_resolver: PodcastArtworkResolver,
        logger: LoggerInterface,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ):
        """
        Use case for ingesting a BATCH of podcasts matching search criteria,
        together with their artwork images and color palettes.

        Args:
            provider: Port used to search the podcasts.
            repository: Port used to read the stored podcasts and store the new ones.
            artwork_resolver: Service that decides and processes the artwork.
            logger: Port used to report podcasts that couldn't be fully ingested.
            max_concurrency: Maximum number of podcasts processed at the same time.
        """
        self._provider = provider
        self._repository = repository
        self._artwork_resolver = artwork_resolver
        self._logger = logger
        self._max_concurrency = max_concurrency

    async def execute(self, criteria: PodcastSearchCriteria) -> IngestionSummary:
        """
        Search the podcasts matching the criteria, process their artwork and
        store them.

        Safe to run repeatedly: podcasts are stored by id, so stored podcasts
        are updated (or left unchanged) instead of duplicated. A podcast that
        fails is counted in the summary and never stops the rest of the batch.

        Args:
            criteria: What to search for.

        Returns:
            How many podcasts were fetched, created, updated, unchanged,
            duplicated within the batch and failed.

        Raises:
            ExternalServiceError: If the search fails (raised by the provider).
        """
        result = await self._provider.search(criteria)
        podcasts = _unique_by_id(result.podcasts)

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def ingest_bounded(podcast: Podcast) -> Status:
            """Ingest a single podcast once a concurrency slot is free."""
            async with semaphore:
                return await self._ingest_one(podcast)

        statuses = await asyncio.gather(*(ingest_bounded(p) for p in podcasts))
        counts = Counter(s.status for s in statuses)

        return IngestionSummary(
            fetched=result.fetched,
            created=counts[StatusType.CREATED],
            updated=counts[StatusType.UPDATED],
            unchanged=counts[StatusType.UNCHANGED],
            duplicates=len(result.podcasts) - len(podcasts),
            failed=counts[StatusType.ERROR] + result.rejected,
        )

    async def _ingest_one(self, podcast: Podcast) -> Status:
        """
        Process the artwork of a single fetched podcast and store it.

        Args:
            podcast: The podcast fetched from the provider.

        Returns:
            The storage status: CREATED, UPDATED, UNCHANGED, or ERROR if the
            podcast could not be read or stored.
        """
        podcast_id = podcast.podcast_id
        try:
            stored = await self._repository.get_podcast_by_id(podcast_id)
            resolution = await self._artwork_resolver.resolve(podcast, stored)
            if resolution.failure_reason is not None:
                self._logger.warning(
                    f"artwork unavailable for podcast {podcast_id}: "
                    f"{resolution.failure_reason}"
                )

            status = await self._repository.store_podcast(
                podcast.model_copy(update={"artwork": resolution.artwork})
            )
        except Exception as e:
            self._logger.error(f"podcast {podcast_id} could not be ingested: {e}")
            return Status(status=StatusType.ERROR, message=str(e))

        if status.status == StatusType.ERROR:
            self._logger.error(
                f"podcast {podcast_id} could not be stored: {status.message}"
            )
        return status


def _unique_by_id(podcasts: list[Podcast]) -> list[Podcast]:
    """
    Drop podcasts whose id already appeared earlier in the list.

    Args:
        podcasts: The podcasts, possibly with repeated ids.

    Returns:
        The podcasts in their original order, keeping the first of each id.
    """
    unique: dict[int, Podcast] = {}
    for podcast in podcasts:
        unique.setdefault(podcast.podcast_id, podcast)
    return list(unique.values())
