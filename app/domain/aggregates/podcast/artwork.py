from pydantic import BaseModel, Field, HttpUrl


class PaletteColor(BaseModel):
    """A color of an image palette and how much of the image it covers."""

    # Lowercase "#rrggbb".
    hex: str = Field(pattern=r"^#[0-9a-f]{6}$")
    # Share of the image's pixels, between 0 and 1.
    proportion: float = Field(ge=0, le=1)


class Artwork(BaseModel):
    """
    The artwork image of a podcast and its color palette.

    It is unprocessed (only source_url is set) until the image is downloaded,
    stored and its palette extracted.
    """

    # URL the image is downloaded from.
    source_url: HttpUrl
    # Where the image was stored, None if it was not processed yet.
    path: str | None = None
    # Dominant color first, empty if it was not processed yet.
    palette: list[PaletteColor] = Field(default_factory=list)
