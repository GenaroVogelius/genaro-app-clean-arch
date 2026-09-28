import pytest
from pydantic import ValidationError

from app.infrastructure.providers.itunes_provider.requests import (
    Attribute,
    Entity,
    ITunesSearchParams,
    Lang,
    Media,
)


def test_defaults_match_api_defaults() -> None:
    params = ITunesSearchParams(term="jack johnson")

    assert params.country == "US"
    assert params.media is Media.ALL
    assert params.entity is None
    assert params.attribute is None
    assert params.limit == 50
    assert params.lang is Lang.EN_US
    assert params.explicit is True


def test_accepts_entity_allowed_for_media() -> None:
    params = ITunesSearchParams(term="love", media=Media.MUSIC, entity=Entity.ALBUM)

    assert params.entity is Entity.ALBUM


def test_rejects_entity_not_allowed_for_media() -> None:
    with pytest.raises(ValidationError, match="not valid for media"):
        ITunesSearchParams(term="love", media=Media.MOVIE, entity=Entity.SONG)


def test_attribute_is_not_cross_checked_against_media() -> None:
    params = ITunesSearchParams(
        term="love", media=Media.MUSIC, attribute=Attribute.ACTOR_TERM
    )

    assert params.attribute is Attribute.ACTOR_TERM


@pytest.mark.parametrize("limit", [0, 201])
def test_rejects_limit_out_of_range(limit: int) -> None:
    with pytest.raises(ValidationError):
        ITunesSearchParams(term="love", limit=limit)


@pytest.mark.parametrize("country", ["us", "USA"])
def test_rejects_non_alpha2_country(country: str) -> None:
    with pytest.raises(ValidationError):
        ITunesSearchParams(term="love", country=country)


def test_rejects_empty_term() -> None:
    with pytest.raises(ValidationError):
        ITunesSearchParams(term="")


def test_to_query_drops_unset_params_and_formats_explicit() -> None:
    params = ITunesSearchParams(
        term="rock and roll", media=Media.PODCAST, entity=Entity.PODCAST, limit=10
    )

    assert params.to_query() == {
        "term": "rock and roll",
        "country": "US",
        "media": "podcast",
        "entity": "podcast",
        "limit": 10,
        "lang": "en_us",
        "explicit": "Yes",
    }


def test_to_query_formats_disabled_explicit_as_no() -> None:
    params = ITunesSearchParams(term="rock", explicit=False)

    assert params.to_query()["explicit"] == "No"
