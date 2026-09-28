from abc import ABC, abstractmethod


class ArtworkStorageInterface(ABC):
    """
    Port for storing artwork images
    """

    @abstractmethod
    async def store(self, podcast_id: int, content: bytes, source_url: str) -> str:
        """
        Store the artwork image of a podcast, replacing any previous one.

        Args:
            podcast_id: id of the podcast the artwork belongs to.
            content: Raw image content.
            source_url: URL the image was downloaded from, so the storage can
                decide how to name or type it.

        Returns:
            Where the image was stored.

        Raises:
            ArtworkUnavailableError: If the image could not be stored.
        """
