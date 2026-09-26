from datetime import datetime

from pydantic import BaseModel

from app.domain.aggregates.podcast import Artwork, Explicitness, PaletteColor, Podcast


class PaletteColorResponse(BaseModel):
    hex: str
    proportion: float

    @classmethod
    def from_entity(cls, color: PaletteColor) -> "PaletteColorResponse":
        """
        Build the API response from a palette color value object.

        Args:
            color: The palette color.

        Returns:
            The palette color as exposed by the API.
        """
        return cls(hex=color.hex, proportion=color.proportion)


class ArtworkResponse(BaseModel):
    source_url: str
    path: str | None
    palette: list[PaletteColorResponse]

    @classmethod
    def from_entity(cls, artwork: Artwork) -> "ArtworkResponse":
        """
        Build the API response from an artwork value object.

        Args:
            artwork: The artwork.

        Returns:
            The artwork as exposed by the API.
        """
        return cls(
            source_url=str(artwork.source_url),
            path=artwork.path,
            palette=[PaletteColorResponse.from_entity(c) for c in artwork.palette],
        )


class PodcastResponse(BaseModel):
    podcast_id: int
    name: str
    author: str
    feed_url: str | None
    view_url: str | None
    genre: str | None
    episode_count: int | None
    release_date: datetime | None
    country: str | None
    explicitness: Explicitness | None
    artwork: ArtworkResponse | None

    @classmethod
    def from_entity(cls, podcast: Podcast) -> "PodcastResponse":
        """
        Build the API response from a podcast domain entity.

        Args:
            podcast: The podcast.

        Returns:
            The podcast as exposed by the API.
        """
        return cls(
            podcast_id=podcast.podcast_id,
            name=podcast.name,
            author=podcast.author,
            feed_url=_str_or_none(podcast.feed_url),
            view_url=_str_or_none(podcast.view_url),
            genre=podcast.genre,
            episode_count=podcast.episode_count,
            release_date=podcast.release_date,
            country=podcast.country,
            explicitness=podcast.explicitness,
            artwork=(
                None
                if podcast.artwork is None
                else ArtworkResponse.from_entity(podcast.artwork)
            ),
        )


def _str_or_none(value: object | None) -> str | None:
    """
    Convert a value (e.g. an HttpUrl) to str, keeping None as None.

    Args:
        value: Value to convert.

    Returns:
        The value as a string, or None.
    """
    return None if value is None else str(value)
