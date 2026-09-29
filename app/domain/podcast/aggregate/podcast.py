from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.domain.podcast.aggregate.artwork import Artwork
from app.domain.podcast.aggregate.podcast_enums import Explicitness


class Podcast(BaseModel):
    """A podcast show, independent of the source it was fetched from."""

    # Id of the podcast in the source it was fetched from.
    podcast_id: int
    name: str
    author: str
    # RSS feed of the show.
    feed_url: HttpUrl | None = None
    view_url: HttpUrl | None = None
    genre: str | None = None
    episode_count: int | None = None
    release_date: datetime | None = None
    # ISO 3166-1 alpha-3 (e.g. "USA").
    country: str | None = None
    explicitness: Explicitness | None = None
    # Artwork image and its palette. Providers set only its source_url; the
    # ingestion processes it. None if the source has no artwork.
    artwork: Artwork | None = None
