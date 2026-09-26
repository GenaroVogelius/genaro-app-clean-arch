import pytest

from app.domain.aggregates.item import Item, ItemId
from app.domain.interfaces.repositories.item import ItemRepositoryInterface
from app.domain.simple_entities.status import Status
from app.domain.use_cases.item.get_item.get_item_use_case import GetItemUseCase


class FakeItemRepository(ItemRepositoryInterface):
    def __init__(self, existing_items: list[Item]):
        self._items = {item.id: item for item in existing_items}

    async def get_item_by_id(self, item_id: ItemId) -> Item | None:
        return self._items.get(item_id)

    async def store_item(self, item: Item) -> Status:
        raise NotImplementedError()


@pytest.mark.asyncio
async def test_get_item_use_case_returns_existing_item() -> None:
    item = Item(name="first item")
    use_case = GetItemUseCase(repository=FakeItemRepository(existing_items=[item]))

    assert await use_case.execute(item.id) == item


@pytest.mark.asyncio
async def test_get_item_use_case_returns_none_when_missing() -> None:
    use_case = GetItemUseCase(repository=FakeItemRepository(existing_items=[]))

    assert await use_case.execute("missing-id") is None
