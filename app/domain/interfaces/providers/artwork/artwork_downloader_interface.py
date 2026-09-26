from abc import ABC, abstractmethod


class ArtworkDownloaderInterface(ABC):
    """
    Port for downloading an artwork image
    """

    @abstractmethod
    async def download(self, url: str) -> bytes:
        """
        Download an image.

        Args:
            url: URL of the image.

        Returns:
            The raw image content.

        Raises:
            ArtworkUnavailableError: If the image could not be downloaded.
        """
