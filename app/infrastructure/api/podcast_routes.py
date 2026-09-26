from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.domain.exceptions import (
    ExternalServiceError,
    NotAPodcastError,
    PodcastNotFoundError,
    PodcastPersistenceError,
)
from app.domain.simple_entities.status import StatusType
from app.domain.use_cases.podcast.get_podcast.get_podcast_use_case import (
    GetPodcastUseCase,
)
from app.domain.use_cases.podcast.ingest_podcast.ingest_podcast_use_case import (
    IngestPodcastUseCase,
)
from app.infrastructure.api.schemas.podcast_schemas import PodcastResponse
from app.infrastructure.api.schemas.status_schemas import StatusResponse
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcasts_repository import (  # noqa: E501
    PodcastsRepository,
)
from app.infrastructure.logger import logger
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


class PodcastRoutes:
    def __init__(
        self,
        ingest_podcast_use_case: IngestPodcastUseCase | None = None,
        get_podcast_use_case: GetPodcastUseCase | None = None,
    ):
        """
        Args:
            ingest_podcast_use_case: Use case that ingests a single podcast.
                Defaults to one backed by the iTunes provider, the MongoDB
                podcasts repository and local artwork storage.
            get_podcast_use_case: Use case that gets a single stored podcast.
                Defaults to one backed by the MongoDB podcasts repository.
        """
        self.router = APIRouter()
        self.get_podcast_use_case = get_podcast_use_case or GetPodcastUseCase(
            repository=PodcastsRepository()
        )
        self.ingest_podcast_use_case = ingest_podcast_use_case or IngestPodcastUseCase(
            provider=ITunesProvider(),
            repository=PodcastsRepository(),
            downloader=HttpArtworkDownloader(),
            storage=LocalArtworkStorage(),
            palette_extractor=PillowColorPaletteExtractor(),
            logger=logger,
        )

        self._setup_routes()

    def _setup_routes(self):
        """Register the podcast routes on the router."""

        @self.router.get("/podcasts/{podcast_id}", response_model=PodcastResponse)
        async def get_podcast(podcast_id: Annotated[int, Path(gt=0)]):
            """
            Get a single stored podcast by its id.
            Responds 404 when no podcast is stored with that id.
            """
            try:
                podcast = await self.get_podcast_use_case.execute(podcast_id)
            except PodcastNotFoundError as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
                ) from e

            return PodcastResponse.from_entity(podcast)

        @self.router.post(
            "/podcasts/{podcast_id}/ingest", response_model=StatusResponse
        )
        async def ingest_podcast(
            podcast_id: Annotated[int, Path(gt=0)], response: Response
        ):
            """
            Ingest a single podcast by its id.
            Responds 201 when the podcast was inserted, 200 when it was updated or
            was already up to date.
            """
            try:
                result = await self.ingest_podcast_use_case.execute(podcast_id)
            except PodcastNotFoundError as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
                ) from e
            except NotAPodcastError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)
                ) from e
            except ExternalServiceError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
                ) from e
            except PodcastPersistenceError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
                ) from e

            if result.status == StatusType.CREATED:
                response.status_code = status.HTTP_201_CREATED
            return StatusResponse.from_entity(result)
