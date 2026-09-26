from decimal import Decimal

from pydantic import BaseModel, Field

# Trimmed real payload from GET https://itunes.apple.com/lookup?id=1200361736
# {
#   "resultCount": 1,
#   "results": [{
#     "wrapperType": "track", "kind": "podcast",
#     "artistId": 121664449, "collectionId": 1200361736, "trackId": 1200361736,
#     "artistName": "The New York Times", "collectionName": "The Daily",
#     "trackName": "The Daily",
#     "artistViewUrl": "https://podcasts.apple.com/us/artist/the-new-york-times/121664449?uo=4",
#     "feedUrl": "https://feeds.simplecast.com/Sl5CSM3S",
#     "artworkUrl100": "https://is1-ssl.mzstatic.com/.../100x100bb.jpg",
#     "collectionPrice": 0.00, "trackPrice": 0.00,
#     "releaseDate": "2026-09-25T09:45:00Z",
#     "collectionExplicitness": "notExplicit", "trackExplicitness": "cleaned",
#     "trackCount": 2730, "trackTimeMillis": 1822,
#     "country": "USA", "currency": "USD", "primaryGenreName": "Daily News"
#   }]
# }


class ITunesResultResponse(BaseModel):
    # Absent on ebook results.
    wrapper_type: str | None = Field(None, alias="wrapperType")
    kind: str | None = Field(None, alias="kind")

    artist_id: int | None = Field(None, alias="artistId")
    artist_name: str | None = Field(None, alias="artistName")
    artist_view_url: str | None = Field(None, alias="artistViewUrl")
    # Returned for artist results instead of artistViewUrl.
    artist_link_url: str | None = Field(None, alias="artistLinkUrl")

    collection_id: int | None = Field(None, alias="collectionId")
    collection_name: str | None = Field(None, alias="collectionName")
    collection_censored_name: str | None = Field(None, alias="collectionCensoredName")
    collection_view_url: str | None = Field(None, alias="collectionViewUrl")
    collection_price: Decimal | None = Field(None, alias="collectionPrice")
    collection_explicitness: str | None = Field(None, alias="collectionExplicitness")

    track_id: int | None = Field(None, alias="trackId")
    track_name: str | None = Field(None, alias="trackName")
    track_censored_name: str | None = Field(None, alias="trackCensoredName")
    track_view_url: str | None = Field(None, alias="trackViewUrl")
    track_price: Decimal | None = Field(None, alias="trackPrice")
    track_explicitness: str | None = Field(None, alias="trackExplicitness")
    track_time_millis: int | None = Field(None, alias="trackTimeMillis")
    track_number: int | None = Field(None, alias="trackNumber")
    track_count: int | None = Field(None, alias="trackCount")
    disc_number: int | None = Field(None, alias="discNumber")
    disc_count: int | None = Field(None, alias="discCount")

    # Used by software and ebook results instead of trackPrice.
    price: Decimal | None = Field(None, alias="price")
    preview_url: str | None = Field(None, alias="previewUrl")
    feed_url: str | None = Field(None, alias="feedUrl")
    artwork_url_60: str | None = Field(None, alias="artworkUrl60")
    artwork_url_100: str | None = Field(None, alias="artworkUrl100")
    country: str | None = Field(None, alias="country")
    currency: str | None = Field(None, alias="currency")
    primary_genre_name: str | None = Field(None, alias="primaryGenreName")
    release_date: str | None = Field(None, alias="releaseDate")
    description: str | None = Field(None, alias="description")
    copyright: str | None = Field(None, alias="copyright")


class ITunesLookupResponse(BaseModel):
    result_count: int = Field(..., alias="resultCount")
    results: list[ITunesResultResponse] = Field(..., alias="results")
