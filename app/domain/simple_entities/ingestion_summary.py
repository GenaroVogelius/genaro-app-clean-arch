from pydantic import BaseModel, Field


class IngestionSummary(BaseModel):
    """Outcome of ingesting a batch of podcasts."""

    # Results returned by the source, including unusable ones.
    fetched: int = Field(default=0, ge=0)
    created: int = Field(default=0, ge=0)
    updated: int = Field(default=0, ge=0)
    # Already stored with the same data.
    unchanged: int = Field(default=0, ge=0)
    # Repeated podcasts within the same batch.
    duplicates: int = Field(default=0, ge=0)
    # Results that couldn't be mapped, read or stored.
    failed: int = Field(default=0, ge=0)

    @property
    def stored(self) -> int:
        """
        Get how many podcasts were written.

        Returns:
            The created plus the updated podcasts.
        """
        return self.created + self.updated

    @property
    def skipped(self) -> int:
        """
        Get how many podcasts needed no write.

        Returns:
            The unchanged podcasts plus the duplicates within the batch.
        """
        return self.unchanged + self.duplicates
