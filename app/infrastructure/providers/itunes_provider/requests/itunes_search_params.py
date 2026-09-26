from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from app.infrastructure.providers.itunes_provider.requests.itunes_enums import (
    MEDIA_ENTITIES,
    Attribute,
    Entity,
    Lang,
    Media,
)

# ISO 3166-1 alpha-2 (e.g. "US").
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class ITunesSearchParams(BaseModel):
    """Validated input for an iTunes Search API query."""

    # Raw text; URL-encoding is an infrastructure concern.
    term: str = Field(min_length=1)
    country: CountryCode = "US"
    media: Media = Media.ALL
    # None means the API default: the track entity for the chosen media.
    entity: Entity | None = None
    # Not cross-checked against media; the API rejects invalid pairs itself.
    attribute: Attribute | None = None
    limit: int = Field(default=50, ge=1, le=200)
    lang: Lang = Lang.EN_US
    explicit: bool = True

    @model_validator(mode="after")
    def check_entity_matches_media(self) -> Self:
        """Ensure `entity` is one of the entities allowed for `media`.

        Returns:
            The validated params.

        Raises:
            ValueError: If `entity` is set and not allowed for `media`.
        """
        if self.entity is not None and self.entity not in MEDIA_ENTITIES[self.media]:
            raise ValueError(
                f"entity '{self.entity}' is not valid for media '{self.media}'"
            )
        return self
