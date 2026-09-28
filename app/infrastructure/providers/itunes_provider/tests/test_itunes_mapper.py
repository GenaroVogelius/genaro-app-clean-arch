from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.aggregates.podcast import Artwork, Explicitness, Podcast
from app.infrastructure.providers.itunes_provider.mapper.itunes_mapper import (
    ITunesMapper,
)
from app.infrastructure.providers.itunes_provider.responses import (
    ITunesResultResponse,
)

mapper = ITunesMapper()


def _podcast_result(**overrides: Any) -> ITunesResultResponse:
    """
    Build a raw iTunes podcast result using the API's camelCase keys.

    Args:
        **overrides: Keys to add or replace in the payload.

    Returns:
        The raw result.
    """
    data: dict[str, Any] = {
        "wrapperType": "track",
        "kind": "podcast",
        "trackId": 1,
        "trackName": "Track Name",
        "collectionId": 1200361736,
        "collectionName": "The Daily",
        "collectionViewUrl": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
        "collectionExplicitness": "notExplicit",
        "artistName": "The New York Times",
        "feedUrl": "https://feeds.simplecast.com/Sl5CSM3S",
        "trackCount": 2730,
        "releaseDate": "2026-09-25T09:45:00Z",
        "country": "USA",
    }
    data.update(overrides)
    return ITunesResultResponse.model_validate(data)


def test_maps_result_to_podcast_preferring_collection_fields() -> None:
    podcast = mapper.map(_podcast_result(), Podcast)

    assert podcast.podcast_id == 1200361736
    assert podcast.name == "The Daily"
    assert podcast.author == "The New York Times"
    assert str(podcast.feed_url) == "https://feeds.simplecast.com/Sl5CSM3S"
    assert (
        str(podcast.view_url)
        == "https://podcasts.apple.com/us/podcast/the-daily/id1200361736"
    )
    assert podcast.episode_count == 2730
    assert podcast.release_date is not None
    assert podcast.release_date.year == 2026


def test_maps_result_to_podcast_falling_back_to_track_fields() -> None:
    raw = _podcast_result(
        collectionId=None,
        collectionName=None,
        collectionViewUrl=None,
        trackId=1200361736,
        trackName="The Daily",
        trackViewUrl="https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
    )

    podcast = mapper.map(raw, Podcast)

    assert podcast.podcast_id == 1200361736
    assert podcast.name == "The Daily"
    assert podcast.view_url is not None


def test_maps_artwork_url_to_unprocessed_artwork() -> None:
    raw = _podcast_result(
        artworkUrl100="https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
    )

    podcast = mapper.map(raw, Podcast)

    assert podcast.artwork == Artwork.model_validate(
        {"source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"}
    )


def test_maps_missing_artwork_url_to_no_artwork() -> None:
    podcast = mapper.map(_podcast_result(), Podcast)

    assert podcast.artwork is None


@pytest.mark.parametrize(
    ("itunes_value", "expected"),
    [
        ("explicit", Explicitness.EXPLICIT),
        ("cleaned", Explicitness.CLEANED),
        ("notExplicit", Explicitness.NOT_EXPLICIT),
        (None, None),
    ],
)
def test_translates_itunes_explicitness_to_domain_values(
    itunes_value: str | None, expected: Explicitness | None
) -> None:
    podcast = mapper.map(_podcast_result(collectionExplicitness=itunes_value), Podcast)

    assert podcast.explicitness is expected


def test_rejects_unknown_explicitness() -> None:
    with pytest.raises(ValueError, match="unknown iTunes explicitness"):
        mapper.map(_podcast_result(collectionExplicitness="sometimes"), Podcast)


def test_rejects_result_without_author() -> None:
    with pytest.raises(ValidationError):
        mapper.map(_podcast_result(artistName=None), Podcast)
