from pathlib import Path

import pytest

from app.domain.ingestion import ArtworkUnavailableError
from app.infrastructure.services.local_artwork_storage.local_artwork_storage import (
    LocalArtworkStorage,
)

ARTWORK_URL = "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"


def read(path: str) -> bytes:
    """Read a stored file (sync helper, kept out of the async tests)."""
    return Path(path).read_bytes()


@pytest.mark.asyncio
async def test_store_writes_file_named_after_podcast(tmp_path: Path) -> None:
    storage = LocalArtworkStorage(base_dir=tmp_path / "artwork")

    path = await storage.store(1200361736, b"image-bytes", ARTWORK_URL)

    assert Path(path) == tmp_path / "artwork" / "1200361736.jpg"
    assert read(path) == b"image-bytes"


@pytest.mark.asyncio
async def test_store_overwrites_previous_file(tmp_path: Path) -> None:
    storage = LocalArtworkStorage(base_dir=tmp_path)
    await storage.store(1, b"old", ARTWORK_URL)

    path = await storage.store(1, b"new", ARTWORK_URL)

    assert read(path) == b"new"


@pytest.mark.asyncio
async def test_store_raises_when_directory_is_not_writable(tmp_path: Path) -> None:
    # A file where the directory should be makes mkdir fail.
    blocker = tmp_path / "artwork"
    blocker.write_bytes(b"")
    storage = LocalArtworkStorage(base_dir=blocker)

    with pytest.raises(ArtworkUnavailableError, match="storage failed"):
        await storage.store(1, b"image-bytes", ARTWORK_URL)


@pytest.mark.asyncio
async def test_store_takes_extension_from_source_url(tmp_path: Path) -> None:
    storage = LocalArtworkStorage(base_dir=tmp_path)

    path = await storage.store(1, b"image-bytes", "https://example.com/a/cover.PNG?x=1")

    assert Path(path) == tmp_path / "1.png"


@pytest.mark.asyncio
async def test_store_defaults_to_jpg_when_source_url_has_no_extension(
    tmp_path: Path,
) -> None:
    storage = LocalArtworkStorage(base_dir=tmp_path)

    path = await storage.store(1, b"image-bytes", "https://example.com/artwork/1")

    assert Path(path) == tmp_path / "1.jpg"
