from pydantic import BaseModel

from app.domain.ingestion import IngestionSummary


class IngestionSummaryResponse(BaseModel):
    fetched: int
    stored: int
    skipped: int
    failed: int
    created: int
    updated: int
    unchanged: int
    duplicates: int

    @classmethod
    def from_entity(cls, summary: IngestionSummary) -> "IngestionSummaryResponse":
        """
        Build the API response from a domain ingestion summary.

        Args:
            summary: The ingestion summary.

        Returns:
            The summary as exposed by the API.
        """
        return cls(
            fetched=summary.fetched,
            stored=summary.stored,
            skipped=summary.skipped,
            failed=summary.failed,
            created=summary.created,
            updated=summary.updated,
            unchanged=summary.unchanged,
            duplicates=summary.duplicates,
        )
