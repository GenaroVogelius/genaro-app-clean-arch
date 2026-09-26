from datetime import datetime

from pydantic import BaseModel, Field


class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1)


class ItemResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
