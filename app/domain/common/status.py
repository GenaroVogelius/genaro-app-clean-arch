from enum import StrEnum

from pydantic import BaseModel, Field


class StatusType(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


class Status(BaseModel):
    status: StatusType
    message: str | None = Field(default=None)
