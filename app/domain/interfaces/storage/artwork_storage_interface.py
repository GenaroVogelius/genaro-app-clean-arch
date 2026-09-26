from abc import ABC, abstractmethod


class ArtworkStorageInterface(ABC):
    """
    Port for storing artwork images
    """

    @abstractmethod
    async def store(self, podcast_id: int, content: bytes, extension: str) -> str:
        """
        Store the artwork image of a podcast, replacing any previous one.

        Args:
            podcast_id: id of the podcast the artwork belongs to.
            content: Raw image content.
            extension: File extension including the dot (e.g. ".jpg").

        Returns:
            Where the image was stored.

        Raises:
            ArtworkUnavailableError: If the image could not be stored.
        """
