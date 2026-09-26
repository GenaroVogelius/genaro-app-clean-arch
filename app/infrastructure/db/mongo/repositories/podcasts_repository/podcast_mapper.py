from datetime import UTC, datetime

from app.domain.aggregates.podcast import Artwork, Podcast
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_document import (  # noqa: E501
    ArtworkEmbedded,
    PaletteColorEmbedded,
    PodcastDocument,
)
from app.infrastructure.mapper.global_mapper import GlobalMapper, maps


def _str_or_none(value: object | None) -> str | None:
    """
    Convert a value (e.g. an HttpUrl) to str, keeping None as None.

    Args:
        value: Value to convert.

    Returns:
        The value as a string, or None.
    """
    return None if value is None else str(value)


def _as_utc(value: datetime | None) -> datetime | None:
    """
    Mark a naive datetime read from MongoDB as UTC.

    MongoDB stores datetimes in UTC but some clients return them naive, which
    would make them compare unequal to the aware datetimes of the domain.

    Args:
        value: Datetime read from the database.

    Returns:
        The datetime as UTC-aware, or None.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _artwork_to_embedded(artwork: Artwork | None) -> ArtworkEmbedded | None:
    """
    Map the artwork of a podcast to its embedded MongoDB shape.

    Args:
        artwork: The artwork, or None.

    Returns:
        The embedded artwork, or None.
    """
    if artwork is None:
        return None
    return ArtworkEmbedded(
        source_url=str(artwork.source_url),
        path=artwork.path,
        palette=[
            PaletteColorEmbedded(hex=color.hex, proportion=color.proportion)
            for color in artwork.palette
        ],
    )


def _embedded_to_artwork(embedded: ArtworkEmbedded | None) -> Artwork | None:
    """
    Map a stored embedded artwork back to the domain value object.

    Args:
        embedded: The embedded artwork, or None.

    Returns:
        The artwork, or None.
    """
    if embedded is None:
        return None
    return Artwork.model_validate(embedded.model_dump())


class PodcastMapper(GlobalMapper):
    @maps(Podcast, PodcastDocument)
    def podcast_to_document(self, podcast: Podcast) -> PodcastDocument:
        """
        Map a Podcast domain entity to its MongoDB document.

        Args:
            podcast: The podcast.

        Returns:
            The document to persist.
        """
        return PodcastDocument(
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
            artwork=_artwork_to_embedded(podcast.artwork),
        )

    @maps(PodcastDocument, Podcast)
    def document_to_podcast(self, document: PodcastDocument) -> Podcast:
        """
        Map a stored MongoDB document back to a Podcast domain entity.

        Args:
            document: The stored document.

        Returns:
            The podcast.
        """
        return Podcast.model_validate(
            {
                "podcast_id": document.podcast_id,
                "name": document.name,
                "author": document.author,
                "feed_url": document.feed_url,
                "view_url": document.view_url,
                "genre": document.genre,
                "episode_count": document.episode_count,
                "release_date": _as_utc(document.release_date),
                "country": document.country,
                "explicitness": document.explicitness,
                "artwork": _embedded_to_artwork(document.artwork),
            }
        )
