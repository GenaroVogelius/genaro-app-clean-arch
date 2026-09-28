from datetime import UTC, datetime

import pytest
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from app.domain.aggregates.podcast import Explicitness, Podcast
from app.domain.exceptions import PodcastRetrievalError
from app.domain.simple_entities.podcast_list_criteria import PodcastListCriteria
from app.domain.simple_entities.status import StatusType
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcast_document import (  # noqa: E501
    PodcastDocument,
)
from app.infrastructure.db.mongo.repositories.podcasts_repository.podcasts_repository import (  # noqa: E501
    MongoPodcastsRepository,
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
    return await MongoPodcastsRepository().get_podcast_by_id(podcast_id)


@pytest.mark.asyncio
async def test_store_podcast_inserts_new_podcast() -> None:
    expected = podcast()

    status = await MongoPodcastsRepository().store_podcast(expected)

    assert status.status == StatusType.CREATED
    assert await stored_podcast(expected.podcast_id) == expected


@pytest.mark.asyncio
async def test_store_podcast_returns_unchanged_when_data_is_the_same() -> None:
    repository = MongoPodcastsRepository()
    await repository.store_podcast(podcast())

    status = await repository.store_podcast(podcast())

    assert status.status == StatusType.UNCHANGED
    assert await PodcastDocument.count() == 1


@pytest.mark.asyncio
async def test_store_podcast_updates_when_data_changed() -> None:
    repository = MongoPodcastsRepository()
    await repository.store_podcast(podcast())
    changed = podcast(episode_count=2731)

    status = await repository.store_podcast(changed)

    assert status.status == StatusType.UPDATED
    assert await stored_podcast(changed.podcast_id) == changed
    assert await PodcastDocument.count() == 1


@pytest.mark.asyncio
async def test_get_podcast_by_id_returns_none_when_missing() -> None:
    assert await MongoPodcastsRepository().get_podcast_by_id(1) is None


@pytest.mark.asyncio
async def test_store_podcast_updates_when_artwork_changed() -> None:
    repository = MongoPodcastsRepository()
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

    await MongoPodcastsRepository().store_podcast(expected)

    assert await stored_podcast(expected.podcast_id) == expected


async def store_all(*podcasts: Podcast) -> MongoPodcastsRepository:
    """Store the given podcasts and return the repository holding them."""
    repository = MongoPodcastsRepository()
    for stored in podcasts:
        await repository.store_podcast(stored)
    return repository


def listed(podcast_id: int, name: str, author: str = "Someone") -> Podcast:
    """Build a minimal podcast to list, with the given id, name and author."""
    return Podcast(podcast_id=podcast_id, name=name, author=author)


@pytest.mark.asyncio
async def test_list_podcasts_returns_every_podcast_without_search() -> None:
    repository = await store_all(listed(2, "Beta"), listed(1, "Alpha"))

    page = await repository.list_podcasts(PodcastListCriteria())

    assert [p.podcast_id for p in page.items] == [1, 2]
    assert page.total == 2
    assert (page.offset, page.limit) == (0, 20)


@pytest.mark.asyncio
async def test_list_podcasts_maps_documents_to_podcasts() -> None:
    expected = podcast()
    repository = await store_all(expected)

    page = await repository.list_podcasts(PodcastListCriteria())

    assert page.items == [expected]


@pytest.mark.asyncio
async def test_list_podcasts_searches_by_name() -> None:
    repository = await store_all(listed(1, "The Daily"), listed(2, "Rock Talk"))

    page = await repository.list_podcasts(PodcastListCriteria(q="daily"))

    assert [p.podcast_id for p in page.items] == [1]
    assert page.total == 1


@pytest.mark.asyncio
async def test_list_podcasts_searches_by_author() -> None:
    repository = await store_all(
        listed(1, "The Daily", author="The New York Times"),
        listed(2, "Rock Talk", author="Rolling Stone"),
    )

    page = await repository.list_podcasts(PodcastListCriteria(q="ROLLING"))

    assert [p.podcast_id for p in page.items] == [2]


@pytest.mark.asyncio
async def test_list_podcasts_matches_name_or_author() -> None:
    repository = await store_all(
        listed(1, "Rock Talk", author="Jane"),
        listed(2, "Jazz Hour", author="Rocky"),
        listed(3, "Jazz Night", author="Jane"),
    )

    page = await repository.list_podcasts(PodcastListCriteria(q="rock"))

    assert [p.podcast_id for p in page.items] == [2, 1]
    assert page.total == 2


@pytest.mark.asyncio
async def test_list_podcasts_matches_search_text_literally() -> None:
    repository = await store_all(listed(1, "a.b (live)"), listed(2, "axb"))

    dotted = await repository.list_podcasts(PodcastListCriteria(q="a.b"))
    parenthesis = await repository.list_podcasts(PodcastListCriteria(q="("))

    assert [p.podcast_id for p in dotted.items] == [1]
    assert [p.podcast_id for p in parenthesis.items] == [1]


@pytest.mark.asyncio
async def test_list_podcasts_paginates_and_counts_every_match() -> None:
    repository = await store_all(
        *(listed(podcast_id, f"Show {podcast_id}") for podcast_id in range(1, 6))
    )

    page = await repository.list_podcasts(PodcastListCriteria(offset=1, limit=2))

    assert [p.podcast_id for p in page.items] == [2, 3]
    assert page.total == 5
    assert (page.offset, page.limit) == (1, 2)


@pytest.mark.asyncio
async def test_list_podcasts_sorts_by_name_then_id() -> None:
    repository = await store_all(
        listed(3, "Same"), listed(1, "Zebra"), listed(2, "Same"), listed(4, "Apple")
    )

    page = await repository.list_podcasts(PodcastListCriteria())

    assert [p.podcast_id for p in page.items] == [4, 2, 3, 1]


@pytest.mark.asyncio
async def test_list_podcasts_returns_empty_page_past_the_end() -> None:
    repository = await store_all(listed(1, "Alpha"))

    page = await repository.list_podcasts(PodcastListCriteria(offset=5))

    assert page.items == []
    assert page.total == 1


@pytest.mark.asyncio
async def test_list_podcasts_after_starts_from_first_id_when_none() -> None:
    repository = await store_all(
        listed(3, "Alpha"), listed(1, "Zebra"), listed(2, "Mango")
    )

    batch = await repository.list_podcasts_after(after_id=None, limit=2)

    assert [p.podcast_id for p in batch] == [1, 2]


@pytest.mark.asyncio
async def test_list_podcasts_after_returns_only_greater_ids() -> None:
    repository = await store_all(
        *(listed(podcast_id, f"Show {podcast_id}") for podcast_id in range(1, 6))
    )

    batch = await repository.list_podcasts_after(after_id=2, limit=2)

    assert [p.podcast_id for p in batch] == [3, 4]


@pytest.mark.asyncio
async def test_list_podcasts_after_returns_empty_past_the_last_id() -> None:
    repository = await store_all(listed(1, "Alpha"))

    assert await repository.list_podcasts_after(after_id=1, limit=10) == []


@pytest.mark.asyncio
async def test_list_podcasts_after_maps_documents_to_podcasts() -> None:
    expected = podcast()
    repository = await store_all(expected)

    assert await repository.list_podcasts_after(after_id=None, limit=10) == [expected]


@pytest.mark.asyncio
async def test_list_podcasts_after_raises_retrieval_error_when_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_find(*args, **kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(PodcastDocument, "find", failing_find)

    with pytest.raises(PodcastRetrievalError):
        await MongoPodcastsRepository().list_podcasts_after(after_id=None, limit=10)
