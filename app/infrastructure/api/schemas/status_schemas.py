from pydantic import BaseModel

from app.domain.common import Status, StatusType


class StatusResponse(BaseModel):
    status: StatusType
    message: str | None

    @classmethod
    def from_entity(cls, status: Status) -> "StatusResponse":
        """
        Build the API response from a domain status.

        Args:
            status: The status.

        Returns:
            The status as exposed by the API.
        """
        return cls(status=status.status, message=status.message)
