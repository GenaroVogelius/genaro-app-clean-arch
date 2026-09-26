from datetime import datetime

from beanie import Document, Indexed
from pydantic import BaseModel

from app.domain.aggregates.podcast import Explicitness


class PaletteColorEmbedded(BaseModel):
    """
    Palette color embedded in a podcast's artwork
    """

    hex: str
    proportion: float


class ArtworkEmbedded(BaseModel):
    """
    Artwork embedded in a podcast
    """

    source_url: str
    path: str | None = None
    palette: list[PaletteColorEmbedded] = []


class PodcastDocument(Document):
    """
    Podcast model
    """

    podcast_id: Indexed(int, unique=True)  # type: ignore[valid-type]
    name: str
    author: str
    feed_url: str | None = None
    view_url: str | None = None
    genre: str | None = None
    episode_count: int | None = None
    release_date: datetime | None = None
    country: str | None = None
    explicitness: Explicitness | None = None
    artwork: ArtworkEmbedded | None = None

    class Settings:
        name = "podcasts"
