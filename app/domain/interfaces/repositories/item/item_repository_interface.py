from abc import ABC, abstractmethod

from app.domain.aggregates.item import Item, ItemId
from app.domain.simple_entities.status import Status


class ItemReaderInterface(ABC):
    """
    Reader interface for the Item data
    """

    @abstractmethod
    async def get_item_by_id(self, item_id: ItemId) -> Item | None:
        pass


class ItemWriterInterface(ABC):
    """
    Writer interface for the Item data
    """

    @abstractmethod
    async def store_item(self, item: Item) -> Status:
        pass


class ItemRepositoryInterface(ItemReaderInterface, ItemWriterInterface):
    pass
