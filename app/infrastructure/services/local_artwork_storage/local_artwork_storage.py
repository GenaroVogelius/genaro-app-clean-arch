import asyncio
from pathlib import Path

from app.config.settings import Settings
from app.domain.exceptions import ArtworkUnavailableError
from app.domain.interfaces.storage import ArtworkStorageInterface


class LocalArtworkStorage(ArtworkStorageInterface):
    def __init__(self, base_dir: str | Path | None = None):
        """
        Create a storage that saves artwork images on the local filesystem.

        Args:
            base_dir: Directory where images are saved.
                Defaults to the ARTWORK_STORAGE_DIR setting.
        """
        self._base_dir = Path(base_dir or Settings().ARTWORK_STORAGE_DIR)

    async def store(self, podcast_id: int, content: bytes, extension: str) -> str:
        """
        Save the image as <base_dir>/<podcast_id><extension>, overwriting any
        previous image of the podcast with the same extension.

        Args:
            podcast_id: id of the podcast the artwork belongs to.
            content: Raw image content.
            extension: File extension including the dot (e.g. ".jpg").

        Returns:
            Path of the saved file.

        Raises:
            ArtworkUnavailableError: If the file could not be written.
        """
        path = self._base_dir / f"{podcast_id}{extension}"
        try:
            await asyncio.to_thread(self._write, path, content)
        except OSError as e:
            raise ArtworkUnavailableError(
                f"storage failed: {e.strerror or type(e).__name__}"
            ) from e
        return str(path)

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        """
        Write the content to the path, creating its directory if needed.

        Args:
            path: File to write.
            content: Bytes to write.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
