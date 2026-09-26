import pytest
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from app.domain.aggregates.item import Item
from app.domain.simple_entities.status import StatusType
from app.infrastructure.db.mongo.repositories.item_repository.item_document import (
    ItemDocument,
)
from app.infrastructure.db.mongo.repositories.item_repository.item_repository import (
    ItemRepository,
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
    await init_beanie(database=database, document_models=[ItemDocument])
    yield


@pytest.mark.asyncio
async def test_store_item_then_get_item_by_id_round_trips() -> None:
    repository = ItemRepository()
    item = Item(name="first item")

    status = await repository.store_item(item)
    stored = await repository.get_item_by_id(item.id)

    assert status.status == StatusType.SUCCESS
    assert stored is not None
    assert stored.id == item.id
    assert stored.name == item.name


@pytest.mark.asyncio
async def test_get_item_by_id_returns_none_when_missing() -> None:
    assert await ItemRepository().get_item_by_id("missing-id") is None
