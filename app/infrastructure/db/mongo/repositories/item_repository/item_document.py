from datetime import datetime

from beanie import Document, Indexed


class ItemDocument(Document):
    """
    Item model
    """

    item_id: Indexed(str, unique=True)  # type: ignore[valid-type]
    name: str
    created_at: datetime

    class Settings:
        name = "items"
