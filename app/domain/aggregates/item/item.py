from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

ItemId = str


class Item(BaseModel):
    id: ItemId = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
