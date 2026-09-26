from app.domain.aggregates.item import Item, ItemId
from app.domain.interfaces.mapper import MapperInterface
from app.domain.interfaces.repositories.item import ItemRepositoryInterface
from app.domain.simple_entities.status import Status, StatusType
from app.infrastructure.db.mongo.repositories.item_repository.item_document import (
    ItemDocument,
)
from app.infrastructure.db.mongo.repositories.item_repository.item_mapper import (
    ItemMapper,
)
from app.infrastructure.logger import logger


class ItemRepository(ItemRepositoryInterface):
    def __init__(self, mapper: MapperInterface | None = None):
        self._mapper = mapper or ItemMapper()

    async def get_item_by_id(self, item_id: ItemId) -> Item | None:
        document = await ItemDocument.find_one(ItemDocument.item_id == item_id)
        if document is None:
            return None
        return self._mapper.map(document, Item)

    async def store_item(self, item: Item) -> Status:
        try:
            await self._mapper.map(item, ItemDocument).insert()
        except Exception as e:
            logger.error(f"Error storing item {item.id}: {e}")
            return Status(status=StatusType.ERROR, message=str(e))
        return Status(status=StatusType.SUCCESS, message=f"stored item {item.id}")
