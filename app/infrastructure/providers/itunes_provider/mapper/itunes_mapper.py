from app.domain.podcast.aggregate import Explicitness, Podcast
from app.infrastructure.mapper.global_mapper import GlobalMapper, maps
from app.infrastructure.providers.itunes_provider.responses import (
    ITunesResultResponse,
)

_EXPLICITNESS_BY_ITUNES_VALUE: dict[str, Explicitness] = {
    "explicit": Explicitness.EXPLICIT,
    "cleaned": Explicitness.CLEANED,
    "notExplicit": Explicitness.NOT_EXPLICIT,
}


def _explicitness(value: str | None) -> Explicitness | None:
    """
    Translate an iTunes explicitness value into the domain enum.

    Args:
        value: Raw iTunes value (e.g. "notExplicit").

    Returns:
        The domain explicitness, or None if iTunes didn't send one.

    Raises:
        ValueError: If the value is not a known iTunes explicitness.
    """
    if value is None:
        return None
    if value not in _EXPLICITNESS_BY_ITUNES_VALUE:
        raise ValueError(f"unknown iTunes explicitness '{value}'")
    return _EXPLICITNESS_BY_ITUNES_VALUE[value]


class ITunesMapper(GlobalMapper):
    @maps(ITunesResultResponse, Podcast)
    def response_to_podcast(self, response: ITunesResultResponse) -> Podcast:
        """
        Map a raw iTunes result of kind podcast to a Podcast domain entity.

        iTunes models a show as a track whose collection is the show itself, so
        collection fields are preferred and track fields are the fallback.

        Args:
            response: Raw iTunes result of kind podcast.

        Returns:
            The podcast.

        Raises:
            ValueError: If the result lacks the fields a podcast requires or has
                values that can't be translated (pydantic ValidationError is a
                ValueError).
        """
        return Podcast.model_validate(
            {
                "podcast_id": response.collection_id or response.track_id,
                "name": response.collection_name or response.track_name,
                "author": response.artist_name,
                "feed_url": response.feed_url,
                "view_url": response.collection_view_url or response.track_view_url,
                "genre": response.primary_genre_name,
                "episode_count": response.track_count,
                "release_date": response.release_date,
                "country": response.country,
                "explicitness": _explicitness(response.collection_explicitness),
                "artwork": (
                    {"source_url": response.artwork_url_100}
                    if response.artwork_url_100
                    else None
                ),
            }
        )
