import asyncio
from io import BytesIO
from typing import cast

from PIL import Image, UnidentifiedImageError

from app.config.settings import Settings
from app.domain.aggregates.podcast import PaletteColor
from app.domain.exceptions import ArtworkUnavailableError
from app.domain.interfaces.services import ColorPaletteExtractorInterface

# Images are shrunk to at most this size before quantizing; plenty for a palette.
THUMBNAIL_SIZE = (150, 150)


class PillowColorPaletteExtractor(ColorPaletteExtractorInterface):
    def __init__(self, size: int | None = None):
        """
        Create a palette extractor based on Pillow's median cut quantization.

        Args:
            size: Maximum number of colors in the palette.
                Defaults to the ARTWORK_PALETTE_SIZE setting.
        """
        self._size = size or Settings().ARTWORK_PALETTE_SIZE

    async def extract(self, content: bytes) -> list[PaletteColor]:
        """
        Extract the dominant colors of an image.

        Args:
            content: Raw image content.

        Returns:
            Up to `size` colors, dominant first, with the share of pixels each
            one covers.

        Raises:
            ArtworkUnavailableError: If the content is not a readable image.
        """
        try:
            return await asyncio.to_thread(self._extract, content)
        except (UnidentifiedImageError, OSError) as e:
            raise ArtworkUnavailableError("invalid image") from e

    def _extract(self, content: bytes) -> list[PaletteColor]:
        """
        Blocking palette extraction, run in a worker thread.

        Args:
            content: Raw image content.

        Returns:
            The palette, dominant color first.
        """
        with Image.open(BytesIO(content)) as image:
            rgb = image.convert("RGB")
        rgb.thumbnail(THUMBNAIL_SIZE)
        quantized = rgb.quantize(colors=self._size, method=Image.Quantize.MEDIANCUT)

        palette = quantized.getpalette() or []
        # A quantized ("P" mode) image reports (count, palette index) pairs.
        counts = cast(list[tuple[int, int]], quantized.getcolors() or [])
        counts.sort(reverse=True)
        total = sum(count for count, _ in counts)
        return [
            PaletteColor(
                hex="#{:02x}{:02x}{:02x}".format(*palette[index * 3 : index * 3 + 3]),
                proportion=round(count / total, 4),
            )
            for count, index in counts
        ]
