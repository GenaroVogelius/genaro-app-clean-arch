from pydantic import BaseModel, Field

from app.domain.podcast.aggregate import Podcast


class PodcastPage(BaseModel):
    """A page of stored podcasts and how many podcasts matched in total."""

    items: list[Podcast] = Field(default_factory=list)
    # Podcasts matching the criteria, before pagination.
    total: int = Field(default=0, ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
