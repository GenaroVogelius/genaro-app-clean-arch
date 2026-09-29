from pydantic import BaseModel, Field

from app.domain.podcast.aggregate import Artwork


class ArtworkResolution(BaseModel):
    """Outcome of deciding the artwork of a podcast about to be stored."""

    # Artwork to store, None if the podcast has none.
    artwork: Artwork | None = Field(default=None)
    # Why the artwork couldn't be processed, None if there was no problem.
    failure_reason: str | None = Field(default=None)
