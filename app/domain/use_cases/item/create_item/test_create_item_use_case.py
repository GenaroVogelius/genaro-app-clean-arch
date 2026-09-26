import pytest

from app.domain.aggregates.item import Item, ItemId
from app.domain.interfaces.repositories.item import ItemRepositoryInterface
from app.domain.simple_entities.status import Status, StatusType
from app.domain.use_cases.item.create_item.create_item_use_case import (
    CreateItemUseCase,
)


class FakeItemRepository(ItemRepositoryInterface):
    def __init__(self, store_status: StatusType = StatusType.SUCCESS):
        self._store_status = store_status
        self.stored_items: list[Item] = []

    async def get_item_by_id(self, item_id: ItemId) -> Item | None:
        raise NotImplementedError()

    async def store_item(self, item: Item) -> Status:
        if self._store_status == StatusType.SUCCESS:
            self.stored_items.append(item)
        return Status(status=self._store_status)


@pytest.mark.asyncio
async def test_create_item_use_case_stores_item() -> None:
    repository = FakeItemRepository()
    item = Item(name="first item")

    status = await CreateItemUseCase(repository=repository).execute(item)

    assert status.status == StatusType.SUCCESS
    assert repository.stored_items == [item]


@pytest.mark.asyncio
async def test_create_item_use_case_propagates_repository_error() -> None:
    repository = FakeItemRepository(store_status=StatusType.ERROR)

    status = await CreateItemUseCase(repository=repository).execute(Item(name="x"))

    assert status.status == StatusType.ERROR
    assert repository.stored_items == []
