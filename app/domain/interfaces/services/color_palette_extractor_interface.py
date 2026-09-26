from abc import ABC, abstractmethod

from app.domain.aggregates.podcast import PaletteColor


class ColorPaletteExtractorInterface(ABC):
    """
    Port for extracting the color palette of an image
    """

    @abstractmethod
    async def extract(self, content: bytes) -> list[PaletteColor]:
        """
        Extract the dominant colors of an image.

        Args:
            content: Raw image content.

        Returns:
            The palette, dominant color first.

        Raises:
            ArtworkUnavailableError: If the content is not a readable image.
        """
