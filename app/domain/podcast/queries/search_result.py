from pydantic import BaseModel, Field

from app.domain.podcast.aggregate import Podcast


class PodcastSearchResult(BaseModel):
    """The podcasts a search returned, and how many results were unusable."""

    podcasts: list[Podcast] = Field(default_factory=list)
    # Results the source returned that couldn't be turned into a Podcast.
    rejected: int = Field(default=0, ge=0)

    @property
    def fetched(self) -> int:
        """
        Get how many results the source returned.

        Returns:
            The number of usable podcasts plus the rejected results.
        """
        return len(self.podcasts) + self.rejected
