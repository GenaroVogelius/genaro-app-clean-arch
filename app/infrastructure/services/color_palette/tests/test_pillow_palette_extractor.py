from io import BytesIO

import pytest
from PIL import Image

from app.domain.ingestion import ArtworkUnavailableError
from app.infrastructure.services.color_palette.pillow_palette_extractor import (
    PillowColorPaletteExtractor,
)


def red_and_blue_png() -> bytes:
    """Build a 100x100 PNG that is 75% red (left) and 25% blue (right)."""
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    image.paste((0, 0, 255), (75, 0, 100, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_extract_returns_dominant_color_first() -> None:
    palette = await PillowColorPaletteExtractor(size=5).extract(red_and_blue_png())

    assert [color.hex for color in palette] == ["#ff0000", "#0000ff"]
    assert palette[0].proportion == pytest.approx(0.75)
    assert palette[1].proportion == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_extract_raises_on_invalid_image() -> None:
    with pytest.raises(ArtworkUnavailableError, match="invalid image"):
        await PillowColorPaletteExtractor().extract(b"not an image")
