from app.domain.aggregates.item import Item
from app.infrastructure.db.mongo.repositories.item_repository.item_document import (
    ItemDocument,
)
from app.infrastructure.mapper.global_mapper import GlobalMapper, maps


class ItemMapper(GlobalMapper):
    @maps(Item, ItemDocument)
    def item_to_document(self, item: Item) -> ItemDocument:
        return ItemDocument(item_id=item.id, name=item.name, created_at=item.created_at)

    @maps(ItemDocument, Item)
    def document_to_item(self, document: ItemDocument) -> Item:
        return Item(id=document.item_id, name=document.name, created_at=document.created_at)
