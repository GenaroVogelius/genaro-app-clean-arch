from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]

    @classmethod
    def from_healthy(cls, healthy: bool) -> "HealthResponse":
        """
        Build the API response from the outcome of a health check.

        Args:
            healthy: Whether the checked dependency is reachable.

        Returns:
            The health status as exposed by the API.
        """
        return cls(status="ok" if healthy else "unavailable")
