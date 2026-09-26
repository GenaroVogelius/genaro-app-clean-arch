import httpx

from app.config.settings import Settings
from app.domain.aggregates.podcast import Podcast
from app.domain.exceptions import ExternalServiceError, NotAPodcastError
from app.domain.interfaces.mapper import MapperInterface
from app.domain.interfaces.providers.podcasts import PodcastLookupProviderInterface
from app.infrastructure.logger import logger
from app.infrastructure.providers.itunes_provider.mapper.itunes_mapper import (
    ITunesMapper,
)
from app.infrastructure.providers.itunes_provider.responses import (
    ITunesLookupResponse,
)

# iTunes `kind` of a podcast show.
PODCAST_KIND = "podcast"


class ITunesProvider(PodcastLookupProviderInterface):
    def __init__(
        self,
        mapper: MapperInterface | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """
        Create a provider for the iTunes Lookup API.

        Args:
            mapper: Maps raw iTunes results to domain entities.
            transport: Optional httpx transport, used by tests to stub iTunes.
        """
        settings = Settings()
        self._mapper = mapper or ITunesMapper()
        self._transport = transport
        self._base_url = settings.ITUNES_BASE_URL
        self._timeout = settings.ITUNES_TIMEOUT_SECONDS

    async def lookup_by_id(self, podcast_id: int) -> Podcast | None:
        """
        Look up a podcast by its iTunes id via the iTunes Lookup API.

        Args:
            podcast_id: iTunes id of the podcast (its collection id).

        Returns:
            The podcast, or None if iTunes has nothing for that id.

        Raises:
            NotAPodcastError: If the id refers to something other than a podcast.
            ExternalServiceError: If the request fails or the payload can't be
                mapped to a domain entity.
        """
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.get("/lookup", params={"id": podcast_id})
                response.raise_for_status()

            lookup = ITunesLookupResponse.model_validate(response.json())
            if not lookup.results:
                return None

            raw = lookup.results[0]
            if raw.kind != PODCAST_KIND:
                raise NotAPodcastError(f"iTunes id {podcast_id} is not a podcast")

            return self._mapper.map(raw, Podcast)
        except (httpx.HTTPError, ValueError) as e:
            # ValueError covers invalid JSON and pydantic ValidationError.
            logger.error(f"iTunes lookup failed for id {podcast_id}: {e}")
            raise ExternalServiceError(
                f"iTunes lookup failed for id {podcast_id}"
            ) from e
