from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import StreamingResponse

from app.domain.common import ExternalServiceError, StatusType
from app.domain.podcast.exceptions import (
    NotAPodcastError,
    PodcastNotFoundError,
    PodcastPersistenceError,
    PodcastRetrievalError,
)
from app.domain.podcast.queries import PodcastListCriteria, PodcastSearchCriteria
from app.infrastructure.api.dependencies.common import LoggerDep, require_api_key
from app.infrastructure.api.dependencies.podcasts import (
    ExportPodcastsUseCaseDep,
    GetPodcastUseCaseDep,
    HealthCheckDep,
    IngestPodcastsUseCaseDep,
    IngestPodcastUseCaseDep,
    ListPodcastsUseCaseDep,
)
from app.infrastructure.api.rate_limit import rate_limit_exempt
from app.infrastructure.api.schemas.health_schemas import HealthResponse
from app.infrastructure.api.schemas.ingestion_summary_schemas import (
    IngestionSummaryResponse,
)
from app.infrastructure.api.schemas.podcast_schemas import (
    PodcastPageResponse,
    PodcastResponse,
)
from app.infrastructure.api.schemas.status_schemas import StatusResponse
from app.infrastructure.api.serializers import PodcastCsvSerializer

# Defaults of the bulk ingestion: a batch of rock & roll podcasts.
DEFAULT_SEARCH_TERM = "rock and roll"
DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 200
DEFAULT_SEARCH_COUNTRY = "US"

# Pagination of the stored podcasts listing.
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
MAX_LIST_QUERY_LENGTH = 200

# Media type of the podcasts export.
EXPORT_MEDIA_TYPE = "text/csv; charset=utf-8"

router = APIRouter()

# Every route but the health check requires a valid API key.
protected = [Depends(require_api_key)]


# Registered before "/podcasts/{podcast_id}" so "health" is not taken as a
# podcast id. Exempt from the rate limit: probes poll it on a schedule, and a
# 429 would take a healthy instance out of rotation.
@router.get("/podcasts/health", response_model=HealthResponse)
@rate_limit_exempt
async def health(response: Response, health_check: HealthCheckDep):
    """
    Report whether the podcasts service can reach its backing store.
    Responds 200 when it is reachable, 503 when it is not.
    """
    healthy = await health_check()
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse.from_healthy(healthy)


@router.get(
    "/podcasts",
    response_model=PodcastPageResponse,
    dependencies=protected,
)
async def list_podcasts(
    use_case: ListPodcastsUseCaseDep,
    q: Annotated[str | None, Query(max_length=MAX_LIST_QUERY_LENGTH)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
):
    """
    List stored podcasts sorted by name, a page at a time.
    When q is given, only podcasts whose name or author contains it (ignoring
    case) are listed. Responds 200 with the page and the total number of
    matching podcasts.
    """
    criteria = PodcastListCriteria(q=q, offset=offset, limit=limit)
    page = await use_case.execute(criteria)
    return PodcastPageResponse.from_entity(page)


# Registered before "/podcasts/{podcast_id}" so "export" is not taken as a
# podcast id.
@router.get(
    "/podcasts/export",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
    dependencies=protected,
)
async def export_podcasts(use_case: ExportPodcastsUseCaseDep, logger: LoggerDep):
    """
    Export every stored podcast as a CSV file, sorted by podcast id.
    Memory stays flat however big the catalog is.

    Reading from Mongo: podcasts are read in batches of
    PODCAST_EXPORT_BATCH_SIZE (default 500), sorted by podcast_id. Each
    batch is a short query for ids greater than the last one read, on the
    unique podcast_id index. No database cursor stays open for the whole
    download, and an ingestion running at the same time can't make a row
    appear twice.

    Responding: each batch is written to the response as one CSV chunk and
    then dropped. The file comes as an attachment named
    podcasts-<UTC timestamp>.csv. Its columns are every stored field:
    release_date is ISO 8601, the palette is one cell like
    "#1a2b3c:0.6|#ffffff:0.4", and missing values are empty cells. When no
    podcast is stored, the file has only the header row.

    Errors: the first batch is read before the response starts, so an
    unreachable database returns a 503. If a later batch fails, the 200 has
    already been sent, so the error is logged and the connection is cut. The
    client sees a failed download rather than a partial file that looks
    complete.
    """
    batches = use_case.execute()
    # Read the first batch before responding, so an unreachable store still
    # gets a proper 503 instead of a 200 that breaks halfway.
    try:
        first_batch = await anext(batches)
    except StopAsyncIteration:
        first_batch = []
    except PodcastRetrievalError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e

    serializer = PodcastCsvSerializer()

    async def csv_chunks() -> AsyncIterator[str]:
        """
        Yield the CSV header, then one chunk of rows per batch.

        Raises:
            Exception: Any error reading a later batch, re-raised after
                logging it so the server aborts the response.
        """
        yield serializer.header()
        yield serializer.rows(first_batch)
        try:
            async for batch in batches:
                yield serializer.rows(batch)
        except Exception as e:
            logger.error(f"Podcast export aborted mid-stream: {e}")
            raise

    filename = f"podcasts-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.csv"
    return StreamingResponse(
        csv_chunks(),
        media_type=EXPORT_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/podcasts/{podcast_id}",
    response_model=PodcastResponse,
    dependencies=protected,
)
async def get_podcast(
    podcast_id: Annotated[int, Path(gt=0)], use_case: GetPodcastUseCaseDep
):
    """
    Get a single stored podcast by its id.
    Responds 404 when no podcast is stored with that id.
    """
    try:
        podcast = await use_case.execute(podcast_id)
    except PodcastNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return PodcastResponse.from_entity(podcast)


@router.post(
    "/podcasts/{podcast_id}/ingest",
    response_model=StatusResponse,
    dependencies=protected,
)
async def ingest_podcast(
    podcast_id: Annotated[int, Path(gt=0)],
    response: Response,
    use_case: IngestPodcastUseCaseDep,
):
    """
    Ingest a single podcast by its id.
    Responds 201 when the podcast was inserted, 200 when it was updated or
    was already up to date.
    """
    try:
        result = await use_case.execute(podcast_id)
    except PodcastNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
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


@router.post(
    "/podcasts/ingest",
    response_model=IngestionSummaryResponse,
    dependencies=protected,
)
async def ingest_podcasts(
    use_case: IngestPodcastsUseCaseDep,
    term: Annotated[str, Query(min_length=1)] = DEFAULT_SEARCH_TERM,
    limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = DEFAULT_SEARCH_LIMIT,
    country: Annotated[str, Query(pattern=r"^[A-Z]{2}$")] = DEFAULT_SEARCH_COUNTRY,
):
    """
    Ingest a batch of podcasts matching a search, rock & roll by default.
    Safe to call repeatedly: stored podcasts are updated or skipped,
    never duplicated. Responds 200 with how many podcasts were fetched,
    stored, skipped and failed, or 502 when the search itself fails.
    """
    criteria = PodcastSearchCriteria(term=term, limit=limit, country=country)
    try:
        summary = await use_case.execute(criteria)
    except ExternalServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        ) from e

    return IngestionSummaryResponse.from_entity(summary)
