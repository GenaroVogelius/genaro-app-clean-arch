import csv
import io
from collections.abc import Iterable

from app.domain.aggregates.podcast import Artwork, Podcast

# Separates the colors of the palette, and each color's hex from its proportion.
PALETTE_COLOR_SEPARATOR = "|"
PALETTE_PROPORTION_SEPARATOR = ":"


class PodcastCsvSerializer:
    """
    Turns podcasts into CSV text, one chunk per batch, so an export can be
    streamed without holding every row in memory.
    """

    COLUMNS: tuple[str, ...] = (
        "podcast_id",
        "name",
        "author",
        "feed_url",
        "view_url",
        "genre",
        "episode_count",
        "release_date",
        "country",
        "explicitness",
        "artwork_source_url",
        "artwork_path",
        "artwork_palette",
    )

    def header(self) -> str:
        """
        Build the CSV header row.

        Returns:
            The column names as a CSV line.
        """
        return self._write([self.COLUMNS])

    def rows(self, podcasts: list[Podcast]) -> str:
        """
        Build the CSV rows of a batch of podcasts.

        Args:
            podcasts: The podcasts of the batch.

        Returns:
            One CSV line per podcast, in the order of COLUMNS. Empty when the
            batch is empty.
        """
        return self._write(self._row(podcast) for podcast in podcasts)

    @staticmethod
    def _write(rows: Iterable[Iterable[object]]) -> str:
        """
        Write rows as CSV text, quoting cells that need it.

        Args:
            rows: The rows to write.

        Returns:
            The rows as CSV lines.
        """
        buffer = io.StringIO()
        csv.writer(buffer).writerows(rows)
        return buffer.getvalue()

    @staticmethod
    def _row(podcast: Podcast) -> list[object]:
        """
        Flatten a podcast into the cells of its CSV row.

        Args:
            podcast: The podcast.

        Returns:
            The cells in the order of COLUMNS, with None as an empty cell.
        """
        artwork = podcast.artwork
        return [
            podcast.podcast_id,
            podcast.name,
            podcast.author,
            _cell(podcast.feed_url),
            _cell(podcast.view_url),
            _cell(podcast.genre),
            _cell(podcast.episode_count),
            "" if podcast.release_date is None else podcast.release_date.isoformat(),
            _cell(podcast.country),
            "" if podcast.explicitness is None else podcast.explicitness.value,
            "" if artwork is None else str(artwork.source_url),
            "" if artwork is None else _cell(artwork.path),
            _palette(artwork),
        ]


def _cell(value: object | None) -> object:
    """
    Convert a value to a CSV cell, writing None as an empty cell.

    Args:
        value: The value.

    Returns:
        An empty string for None, the value as a string otherwise.
    """
    return "" if value is None else str(value)


def _palette(artwork: Artwork | None) -> str:
    """
    Join the palette of an artwork into one cell, e.g. "#1a2b3c:0.6|#ffffff:0.4".

    Args:
        artwork: The artwork, or None.

    Returns:
        The joined palette, or an empty string when there is no palette.
    """
    if artwork is None:
        return ""
    return PALETTE_COLOR_SEPARATOR.join(
        f"{color.hex}{PALETTE_PROPORTION_SEPARATOR}{color.proportion}"
        for color in artwork.palette
    )
