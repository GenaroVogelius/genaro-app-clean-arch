from app.domain.aggregates.item import Item
from app.domain.interfaces.repositories.item import ItemWriterInterface
from app.domain.simple_entities.status import Status


class CreateItemUseCase:
    def __init__(self, repository: ItemWriterInterface):
        self._repository = repository

    async def execute(self, item: Item) -> Status:
        """
        Persist a new item.
        """
        return await self._repository.store_item(item)
