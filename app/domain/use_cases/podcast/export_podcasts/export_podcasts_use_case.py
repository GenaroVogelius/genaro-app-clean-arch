from collections.abc import AsyncIterator

from app.domain.aggregates.podcast import Podcast
from app.domain.interfaces.repositories.podcasts import PodcastsExporterInterface

DEFAULT_BATCH_SIZE = 500


class ExportPodcastsUseCase:
    def __init__(
        self,
        repository: PodcastsExporterInterface,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        """
        Use case for exporting EVERY stored podcast, a batch at a time, so the
        whole catalog is never held in memory.

        Args:
            repository: Port used to read the stored podcasts in batches.
            batch_size: Maximum number of podcasts read per batch.
        """
        self._repository = repository
        self._batch_size = batch_size

    async def execute(self) -> AsyncIterator[list[Podcast]]:
        """
        Read every stored podcast in batches sorted by id, each batch
        continuing after the last id of the previous one.

        Yields:
            Non-empty batches of at most batch_size podcasts, sorted by id.

        Raises:
            PodcastRetrievalError: A batch could not be read.
        """
        after_id: int | None = None
        while True:
            batch = await self._repository.list_podcasts_after(
                after_id=after_id, limit=self._batch_size
            )
            if batch:
                yield batch
            if len(batch) < self._batch_size:
                return
            after_id = batch[-1].podcast_id
