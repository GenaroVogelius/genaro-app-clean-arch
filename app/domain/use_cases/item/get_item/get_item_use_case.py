from app.domain.aggregates.item import Item, ItemId
from app.domain.interfaces.repositories.item import ItemReaderInterface


class GetItemUseCase:
    def __init__(self, repository: ItemReaderInterface):
        self._repository = repository

    async def execute(self, item_id: ItemId) -> Item | None:
        """
        Retrieve an item by its id, or None if it does not exist.
        """
        return await self._repository.get_item_by_id(item_id)
