from datetime import UTC, datetime

import pytest
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from app.domain.aggregates.podcast import Explicitness, Podcast
from app.domain.simple_entities.status import StatusType
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_document import (  # noqa: E501
    PodcastDocument,
)
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcasts_repository import (  # noqa: E501
    PodcastsRepository,
)


@pytest.fixture(autouse=True)
async def mongo_db():
    database = AsyncMongoMockClient()["test-db"]

    # Beanie 2.x passes kwargs to list_collection_names that mongomock doesn't support.
    list_collection_names = database.list_collection_names

    async def _list_collection_names(*args, **kwargs):
        kwargs.pop("authorizedCollections", None)
        kwargs.pop("nameOnly", None)
        return await list_collection_names(*args, **kwargs)

    database.list_collection_names = _list_collection_names
    await init_beanie(database=database, document_models=[PodcastDocument])
    yield


def podcast(**overrides) -> Podcast:
    """Build a podcast resembling The Daily, with optional field overrides."""
    return Podcast.model_validate(
        {
            "podcast_id": 1200361736,
            "name": "The Daily",
            "author": "The New York Times",
            "feed_url": "https://feeds.simplecast.com/Sl5CSM3S",
            "view_url": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
            "genre": "Daily News",
            "episode_count": 2730,
            "release_date": datetime(2025, 1, 2, 10, 0, tzinfo=UTC),
            "country": "USA",
            "explicitness": Explicitness.NOT_EXPLICIT,
            "artwork": {
                "source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
                "path": "media/artwork/1200361736.jpg",
                "palette": [
                    {"hex": "#1a2b3c", "proportion": 0.6},
                    {"hex": "#ffffff", "proportion": 0.4},
                ],
            },
            **overrides,
        }
    )


async def stored_podcast(podcast_id: int) -> Podcast | None:
    """Read a stored podcast back as a domain entity."""
    return await PodcastsRepository().get_podcast_by_id(podcast_id)


@pytest.mark.asyncio
async def test_store_podcast_inserts_new_podcast() -> None:
    expected = podcast()

    status = await PodcastsRepository().store_podcast(expected)

    assert status.status == StatusType.CREATED
    assert await stored_podcast(expected.podcast_id) == expected


@pytest.mark.asyncio
async def test_store_podcast_returns_unchanged_when_data_is_the_same() -> None:
    repository = PodcastsRepository()
    await repository.store_podcast(podcast())

    status = await repository.store_podcast(podcast())

    assert status.status == StatusType.UNCHANGED
    assert await PodcastDocument.count() == 1


@pytest.mark.asyncio
async def test_store_podcast_updates_when_data_changed() -> None:
    repository = PodcastsRepository()
    await repository.store_podcast(podcast())
    changed = podcast(episode_count=2731)

    status = await repository.store_podcast(changed)

    assert status.status == StatusType.UPDATED
    assert await stored_podcast(changed.podcast_id) == changed
    assert await PodcastDocument.count() == 1


@pytest.mark.asyncio
async def test_get_podcast_by_id_returns_none_when_missing() -> None:
    assert await PodcastsRepository().get_podcast_by_id(1) is None


@pytest.mark.asyncio
async def test_store_podcast_updates_when_artwork_changed() -> None:
    repository = PodcastsRepository()
    await repository.store_podcast(podcast())
    changed = podcast(artwork=None)

    status = await repository.store_podcast(changed)

    assert status.status == StatusType.UPDATED
    assert await stored_podcast(changed.podcast_id) == changed


@pytest.mark.asyncio
async def test_store_podcast_round_trips_unprocessed_artwork() -> None:
    expected = podcast(
        artwork={"source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"}
    )

    await PodcastsRepository().store_podcast(expected)

    assert await stored_podcast(expected.podcast_id) == expected
