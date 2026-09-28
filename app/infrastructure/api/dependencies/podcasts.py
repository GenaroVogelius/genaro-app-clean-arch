from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from app.domain.interfaces.providers.podcasts import (
    PodcastLookupProviderInterface,
    PodcastSearchProviderInterface,
)
from app.domain.interfaces.repositories.podcasts import PodcastsRepositoryInterface
from app.domain.services.podcast_artwork import PodcastArtworkResolver
from app.domain.use_cases.podcast.export_podcasts.export_podcasts_use_case import (
    ExportPodcastsUseCase,
)
from app.domain.use_cases.podcast.get_podcast.get_podcast_use_case import (
    GetPodcastUseCase,
)
from app.domain.use_cases.podcast.ingest_podcast.ingest_podcast_use_case import (
    IngestPodcastUseCase,
)
from app.domain.use_cases.podcast.ingest_podcasts.ingest_podcasts_use_case import (
    IngestPodcastsUseCase,
)
from app.domain.use_cases.podcast.list_podcasts.list_podcasts_use_case import (
    ListPodcastsUseCase,
)
from app.infrastructure.api.dependencies.common import (
    HttpClientDep,
    LoggerDep,
    SettingsDep,
)
from app.infrastructure.db.mongo.database import check_mongo_health
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcasts_repository import (  # noqa: E501
    MongoPodcastsRepository,
)
from app.infrastructure.providers.artwork_provider.http_artwork_downloader import (
    HttpArtworkDownloader,
)
from app.infrastructure.providers.itunes_provider.itunes_provider import ITunesProvider
from app.infrastructure.services.color_palette.pillow_palette_extractor import (
    PillowColorPaletteExtractor,
)
from app.infrastructure.services.local_artwork_storage.local_artwork_storage import (  # noqa: E501
    LocalArtworkStorage,
)

# Async check that tells whether the podcasts' backing store is reachable.
HealthCheck = Callable[[], Awaitable[bool]]


# The HTTP adapters are cached per shared client (maxsize=1): one instance
# while the app's client lives, rebuilt if a new lifespan opens a new client.
@lru_cache(maxsize=1)
def _get_itunes_provider(client: httpx.AsyncClient) -> ITunesProvider:
    """
    Get the iTunes provider shared by the lookup and search dependencies.

    Args:
        client: Shared HTTP client the provider sends its requests with.

    Returns:
        The provider, built once per shared client.
    """
    return ITunesProvider(client=client)


def get_lookup_provider(client: HttpClientDep) -> PodcastLookupProviderInterface:
    """
    Get the provider used to look up a single podcast by its id.

    Args:
        client: Shared HTTP client the provider sends its requests with.

    Returns:
        The shared iTunes provider.
    """
    return _get_itunes_provider(client)


def get_search_provider(client: HttpClientDep) -> PodcastSearchProviderInterface:
    """
    Get the provider used to search podcasts.

    Args:
        client: Shared HTTP client the provider sends its requests with.

    Returns:
        The shared iTunes provider.
    """
    return _get_itunes_provider(client)


@lru_cache
def get_podcasts_repository() -> PodcastsRepositoryInterface:
    """
    Get the repository podcasts are read from and stored in.

    Returns:
        The MongoDB podcasts repository, built once and reused for the life
        of the process.
    """
    return MongoPodcastsRepository()


@lru_cache(maxsize=1)
def get_artwork_resolver(client: HttpClientDep) -> PodcastArtworkResolver:
    """
    Get the service that downloads, stores and extracts the palette of
    podcast artwork.

    Args:
        client: Shared HTTP client the artwork is downloaded with.

    Returns:
        The resolver backed by HTTP downloads, local storage and Pillow,
        built once per shared client.
    """
    return PodcastArtworkResolver(
        downloader=HttpArtworkDownloader(client=client),
        storage=LocalArtworkStorage(),
        palette_extractor=PillowColorPaletteExtractor(),
    )


def get_health_check() -> HealthCheck:
    """
    Get the check telling whether the podcasts' backing store is reachable.

    Returns:
        The MongoDB ping.
    """
    return check_mongo_health


LookupProviderDep = Annotated[
    PodcastLookupProviderInterface, Depends(get_lookup_provider)
]
SearchProviderDep = Annotated[
    PodcastSearchProviderInterface, Depends(get_search_provider)
]
PodcastsRepositoryDep = Annotated[
    PodcastsRepositoryInterface, Depends(get_podcasts_repository)
]
ArtworkResolverDep = Annotated[PodcastArtworkResolver, Depends(get_artwork_resolver)]
HealthCheckDep = Annotated[HealthCheck, Depends(get_health_check)]


def get_podcast_use_case(repository: PodcastsRepositoryDep) -> GetPodcastUseCase:
    """
    Build the use case that gets a single stored podcast.

    Args:
        repository: Repository the podcast is read from.

    Returns:
        The use case.
    """
    return GetPodcastUseCase(repository=repository)


def get_list_podcasts_use_case(
    repository: PodcastsRepositoryDep,
) -> ListPodcastsUseCase:
    """
    Build the use case that lists stored podcasts a page at a time.

    Args:
        repository: Repository the podcasts are listed from.

    Returns:
        The use case.
    """
    return ListPodcastsUseCase(repository=repository)


def get_export_podcasts_use_case(
    repository: PodcastsRepositoryDep,
    settings: SettingsDep,
) -> ExportPodcastsUseCase:
    """
    Build the use case that exports every stored podcast a batch at a time.

    Args:
        repository: Repository the podcasts are read from.
        settings: Settings holding PODCAST_EXPORT_BATCH_SIZE.

    Returns:
        The use case, reading PODCAST_EXPORT_BATCH_SIZE podcasts per batch.
    """
    return ExportPodcastsUseCase(
        repository=repository,
        batch_size=settings.PODCAST_EXPORT_BATCH_SIZE,
    )


def get_ingest_podcast_use_case(
    provider: LookupProviderDep,
    repository: PodcastsRepositoryDep,
    artwork_resolver: ArtworkResolverDep,
    logger: LoggerDep,
) -> IngestPodcastUseCase:
    """
    Build the use case that ingests a single podcast by its id.

    Args:
        provider: Provider the podcast is looked up in.
        repository: Repository the podcast is stored in.
        artwork_resolver: Service that processes the podcast artwork.
        logger: Logger reporting partial failures.

    Returns:
        The use case.
    """
    return IngestPodcastUseCase(
        provider=provider,
        repository=repository,
        artwork_resolver=artwork_resolver,
        logger=logger,
    )


def get_ingest_podcasts_use_case(
    provider: SearchProviderDep,
    repository: PodcastsRepositoryDep,
    artwork_resolver: ArtworkResolverDep,
    logger: LoggerDep,
    settings: SettingsDep,
) -> IngestPodcastsUseCase:
    """
    Build the use case that ingests a batch of podcasts matching a search.

    Args:
        provider: Provider the podcasts are searched in.
        repository: Repository the podcasts are stored in.
        artwork_resolver: Service that processes the podcasts' artwork.
        logger: Logger reporting podcasts that couldn't be fully ingested.
        settings: Settings holding PODCAST_INGEST_CONCURRENCY.

    Returns:
        The use case, processing at most PODCAST_INGEST_CONCURRENCY podcasts
        at the same time.
    """
    return IngestPodcastsUseCase(
        provider=provider,
        repository=repository,
        artwork_resolver=artwork_resolver,
        logger=logger,
        max_concurrency=settings.PODCAST_INGEST_CONCURRENCY,
    )


GetPodcastUseCaseDep = Annotated[GetPodcastUseCase, Depends(get_podcast_use_case)]
ListPodcastsUseCaseDep = Annotated[
    ListPodcastsUseCase, Depends(get_list_podcasts_use_case)
]
ExportPodcastsUseCaseDep = Annotated[
    ExportPodcastsUseCase, Depends(get_export_podcasts_use_case)
]
IngestPodcastUseCaseDep = Annotated[
    IngestPodcastUseCase, Depends(get_ingest_podcast_use_case)
]
IngestPodcastsUseCaseDep = Annotated[
    IngestPodcastsUseCase, Depends(get_ingest_podcasts_use_case)
]
