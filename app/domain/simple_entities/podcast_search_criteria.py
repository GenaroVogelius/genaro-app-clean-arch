from pydantic import BaseModel, Field


class PodcastSearchCriteria(BaseModel):
    """What to search for when fetching a batch of podcasts from a source."""

    # Free text matched by the source (e.g. "rock and roll").
    term: str = Field(min_length=1)
    # Maximum number of results to fetch.
    limit: int = Field(ge=1, le=200)
    # ISO 3166-1 alpha-2 store to search in (e.g. "US").
    country: str = Field(pattern=r"^[A-Z]{2}$")
