from enum import StrEnum

from pydantic import BaseModel, Field


class StatusType(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class Status(BaseModel):
    status: StatusType
    message: str | None = Field(default=None)
