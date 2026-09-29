import csv
import io
from datetime import UTC, datetime

from app.domain.podcast.aggregate import Explicitness, Podcast
from app.infrastructure.api.serializers import PodcastCsvSerializer


def parse(text: str) -> list[list[str]]:
    """Parse CSV text back into its rows."""
    return list(csv.reader(io.StringIO(text)))


def full_podcast() -> Podcast:
    """Build a podcast resembling The Daily, with every field set."""
    return Podcast.model_validate(
        {
            "podcast_id": 1200361736,
            "name": "The Daily",
            "author": "The New York Times",
            "feed_url": "https://feeds.simplecast.com/Sl5CSM3S",
            "view_url": "https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
            "genre": "Daily News",
            "episode_count": 2730,
            "release_date": datetime(2025, 1, 2, 10, 0, tzinfo=UTC),
            "country": "USA",
            "explicitness": Explicitness.NOT_EXPLICIT,
            "artwork": {
                "source_url": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
                "path": "media/artwork/1200361736.jpg",
                "palette": [
                    {"hex": "#1a2b3c", "proportion": 0.6},
                    {"hex": "#ffffff", "proportion": 0.4},
                ],
            },
        }
    )


def test_header_lists_every_column_in_order() -> None:
    assert parse(PodcastCsvSerializer().header()) == [
        [
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
        ]
    ]


def test_rows_flatten_every_field() -> None:
    rows = parse(PodcastCsvSerializer().rows([full_podcast()]))

    assert rows == [
        [
            "1200361736",
            "The Daily",
            "The New York Times",
            "https://feeds.simplecast.com/Sl5CSM3S",
            "https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
            "Daily News",
            "2730",
            "2025-01-02T10:00:00+00:00",
            "USA",
            Explicitness.NOT_EXPLICIT.value,
            "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
            "media/artwork/1200361736.jpg",
            "#1a2b3c:0.6|#ffffff:0.4",
        ]
    ]


def test_rows_write_missing_fields_as_empty_cells() -> None:
    minimal = Podcast(podcast_id=1, name="Show", author="Someone")

    rows = parse(PodcastCsvSerializer().rows([minimal]))

    assert rows == [["1", "Show", "Someone"] + [""] * 10]


def test_rows_leave_path_and_palette_empty_for_unprocessed_artwork() -> None:
    unprocessed = Podcast.model_validate(
        {
            "podcast_id": 1,
            "name": "Show",
            "author": "Someone",
            "artwork": {"source_url": "https://example.com/a.jpg"},
        }
    )

    row = parse(PodcastCsvSerializer().rows([unprocessed]))[0]

    assert row[-3:] == ["https://example.com/a.jpg", "", ""]


def test_rows_quote_commas_quotes_and_newlines() -> None:
    tricky = Podcast(podcast_id=1, name='Rock, "Roll"\nand more', author="A, B")

    rows = parse(PodcastCsvSerializer().rows([tricky]))

    assert rows[0][1:3] == ['Rock, "Roll"\nand more', "A, B"]


def test_rows_write_one_line_per_podcast() -> None:
    podcasts = [Podcast(podcast_id=i, name=f"Show {i}", author="X") for i in (1, 2)]

    rows = parse(PodcastCsvSerializer().rows(podcasts))

    assert [row[0] for row in rows] == ["1", "2"]


def test_rows_of_an_empty_batch_is_empty() -> None:
    assert PodcastCsvSerializer().rows([]) == ""
