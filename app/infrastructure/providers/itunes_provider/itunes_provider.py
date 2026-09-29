import httpx

from app.config.settings import Settings
from app.domain.common import ExternalServiceError
from app.domain.interfaces.mapper import MapperInterface
from app.domain.interfaces.providers.podcasts import (
    PodcastLookupProviderInterface,
    PodcastSearchProviderInterface,
)
from app.domain.podcast.aggregate import Podcast
from app.domain.podcast.exceptions import NotAPodcastError
from app.domain.podcast.queries import PodcastSearchCriteria, PodcastSearchResult
from app.infrastructure.logger import logger
from app.infrastructure.providers.http_client import use_http_client
from app.infrastructure.providers.itunes_provider.mapper.itunes_mapper import (
    ITunesMapper,
)
from app.infrastructure.providers.itunes_provider.requests import (
    Entity,
    ITunesSearchParams,
    Media,
)
from app.infrastructure.providers.itunes_provider.responses import (
    ITunesLookupResponse,
)

# iTunes `kind` of a podcast show.
PODCAST_KIND = "podcast"


class ITunesProvider(PodcastLookupProviderInterface, PodcastSearchProviderInterface):
    def __init__(
        self,
        mapper: MapperInterface | None = None,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """
        Create a provider for the iTunes Lookup and Search APIs.

        Args:
            mapper: Maps raw iTunes results to domain entities.
            client: Shared client the app keeps open, reusing its connections
                across requests. When None, each request opens its own client.
            transport: Optional httpx transport of the per-request client, used
                by tests to stub iTunes. Ignored when a client is given.
        """
        settings = Settings()
        self._mapper = mapper or ITunesMapper()
        self._client = client
        self._transport = transport
        self._base_url = settings.ITUNES_BASE_URL.rstrip("/")
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
        lookup = await self._get(
            "/lookup", {"id": podcast_id}, f"iTunes lookup failed for id {podcast_id}"
        )
        if not lookup.results:
            return None

        raw = lookup.results[0]
        if raw.kind != PODCAST_KIND:
            raise NotAPodcastError(f"iTunes id {podcast_id} is not a podcast")

        try:
            return self._mapper.map(raw, Podcast)
        except ValueError as e:
            # Covers pydantic ValidationError.
            logger.error(f"iTunes lookup failed for id {podcast_id}: {e}")
            raise ExternalServiceError(
                f"iTunes lookup failed for id {podcast_id}"
            ) from e

    async def search(self, criteria: PodcastSearchCriteria) -> PodcastSearchResult:
        """
        Search podcast shows via the iTunes Search API.

        Results that aren't podcasts or can't be mapped to one are logged and
        counted as rejected instead of failing the whole search.

        Args:
            criteria: What to search for.

        Returns:
            The matching podcasts and how many results were rejected.

        Raises:
            ExternalServiceError: If the request fails or the payload is invalid.
        """
        params = ITunesSearchParams(
            term=criteria.term,
            country=criteria.country,
            media=Media.PODCAST,
            entity=Entity.PODCAST,
            limit=criteria.limit,
        )
        search = await self._get(
            "/search", params.to_query(), f"iTunes search failed for '{criteria.term}'"
        )

        podcasts: list[Podcast] = []
        rejected = 0
        for raw in search.results:
            if raw.kind != PODCAST_KIND:
                logger.warning(f"iTunes search skipped a non-podcast ({raw.kind})")
                rejected += 1
                continue
            try:
                podcasts.append(self._mapper.map(raw, Podcast))
            except ValueError as e:
                # Covers pydantic ValidationError.
                logger.warning(
                    f"iTunes search skipped podcast {raw.collection_id}: {e}"
                )
                rejected += 1

        return PodcastSearchResult(podcasts=podcasts, rejected=rejected)

    async def _get(
        self, path: str, params: dict[str, str | int], error_message: str
    ) -> ITunesLookupResponse:
        """
        Call an iTunes endpoint that answers with a list of results.

        Args:
            path: Endpoint path (e.g. "/lookup" or "/search").
            params: Query string parameters.
            error_message: Message of the ExternalServiceError raised on failure.

        Returns:
            The parsed response.

        Raises:
            ExternalServiceError: If the request fails or the payload is invalid.
        """
        try:
            async with use_http_client(self._client, self._transport) as client:
                response = await client.get(
                    f"{self._base_url}{path}", params=params, timeout=self._timeout
                )
                response.raise_for_status()

            return ITunesLookupResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as e:
            # ValueError covers invalid JSON and pydantic ValidationError.
            logger.error(f"{error_message}: {e}")
            raise ExternalServiceError(error_message) from e
