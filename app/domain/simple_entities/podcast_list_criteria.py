from pydantic import BaseModel, Field, field_validator


class PodcastListCriteria(BaseModel):
    """Which stored podcasts to list and which page of them to return."""

    # Free text matched, case-insensitively, against the name or the author.
    # None lists every stored podcast.
    q: str | None = Field(default=None, max_length=200)
    # Number of matching podcasts to skip.
    offset: int = Field(default=0, ge=0)
    # Maximum number of podcasts to return.
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("q")
    @classmethod
    def _blank_q_as_none(cls, value: str | None) -> str | None:
        """
        Strip the search text, treating a blank one as no search at all.

        Args:
            value: The search text as received.

        Returns:
            The stripped text, or None when it is missing or blank.
        """
        if value is None:
            return None
        return value.strip() or None
