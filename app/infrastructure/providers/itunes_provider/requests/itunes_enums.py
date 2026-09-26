from collections.abc import Mapping
from enum import StrEnum


class Media(StrEnum):
    """Media type to search for (`media` param)."""

    MOVIE = "movie"
    PODCAST = "podcast"
    MUSIC = "music"
    MUSIC_VIDEO = "musicVideo"
    AUDIOBOOK = "audiobook"
    SHORT_FILM = "shortFilm"
    TV_SHOW = "tvShow"
    SOFTWARE = "software"
    EBOOK = "ebook"
    ALL = "all"


class Entity(StrEnum):
    """Type of results to return, relative to the media type (`entity` param)."""

    MOVIE_ARTIST = "movieArtist"
    MOVIE = "movie"
    PODCAST_AUTHOR = "podcastAuthor"
    PODCAST = "podcast"
    MUSIC_ARTIST = "musicArtist"
    MUSIC_TRACK = "musicTrack"
    ALBUM = "album"
    MUSIC_VIDEO = "musicVideo"
    MIX = "mix"
    SONG = "song"
    AUDIOBOOK_AUTHOR = "audiobookAuthor"
    AUDIOBOOK = "audiobook"
    SHORT_FILM_ARTIST = "shortFilmArtist"
    SHORT_FILM = "shortFilm"
    TV_EPISODE = "tvEpisode"
    TV_SEASON = "tvSeason"
    SOFTWARE = "software"
    IPAD_SOFTWARE = "iPadSoftware"
    MAC_SOFTWARE = "macSoftware"
    EBOOK = "ebook"
    ALL_ARTIST = "allArtist"
    ALL_TRACK = "allTrack"


class Attribute(StrEnum):
    """Field the search term is matched against (`attribute` param).

    Values come from the legacy version of the iTunes Search API docs; the
    current docs no longer list this parameter. The API itself rejects
    attributes that are not valid for the requested media type.
    """

    ACTOR_TERM = "actorTerm"
    GENRE_INDEX = "genreIndex"
    ARTIST_TERM = "artistTerm"
    SHORT_FILM_TERM = "shortFilmTerm"
    PRODUCER_TERM = "producerTerm"
    RATING_TERM = "ratingTerm"
    DIRECTOR_TERM = "directorTerm"
    RELEASE_YEAR_TERM = "releaseYearTerm"
    FEATURE_FILM_TERM = "featureFilmTerm"
    MOVIE_ARTIST_TERM = "movieArtistTerm"
    MOVIE_TERM = "movieTerm"
    RATING_INDEX = "ratingIndex"
    DESCRIPTION_TERM = "descriptionTerm"
    TITLE_TERM = "titleTerm"
    LANGUAGE_TERM = "languageTerm"
    AUTHOR_TERM = "authorTerm"
    KEYWORDS_TERM = "keywordsTerm"
    MIX_TERM = "mixTerm"
    COMPOSER_TERM = "composerTerm"
    ALBUM_TERM = "albumTerm"
    SONG_TERM = "songTerm"
    TV_EPISODE_TERM = "tvEpisodeTerm"
    SHOW_TERM = "showTerm"
    TV_SEASON_TERM = "tvSeasonTerm"
    SOFTWARE_DEVELOPER = "softwareDeveloper"
    ALL_ARTIST_TERM = "allArtistTerm"
    ALL_TRACK_TERM = "allTrackTerm"


class Lang(StrEnum):
    """Language of the returned results (`lang` param)."""

    EN_US = "en_us"
    JA_JP = "ja_jp"


# Entities allowed for each media type (docs, Table 2-1).
MEDIA_ENTITIES: Mapping[Media, frozenset[Entity]] = {
    Media.MOVIE: frozenset({Entity.MOVIE_ARTIST, Entity.MOVIE}),
    Media.PODCAST: frozenset({Entity.PODCAST_AUTHOR, Entity.PODCAST}),
    Media.MUSIC: frozenset(
        {
            Entity.MUSIC_ARTIST,
            Entity.MUSIC_TRACK,
            Entity.ALBUM,
            Entity.MUSIC_VIDEO,
            Entity.MIX,
            Entity.SONG,
        }
    ),
    Media.MUSIC_VIDEO: frozenset({Entity.MUSIC_ARTIST, Entity.MUSIC_VIDEO}),
    Media.AUDIOBOOK: frozenset({Entity.AUDIOBOOK_AUTHOR, Entity.AUDIOBOOK}),
    Media.SHORT_FILM: frozenset({Entity.SHORT_FILM_ARTIST, Entity.SHORT_FILM}),
    Media.TV_SHOW: frozenset({Entity.TV_EPISODE, Entity.TV_SEASON}),
    Media.SOFTWARE: frozenset(
        {Entity.SOFTWARE, Entity.IPAD_SOFTWARE, Entity.MAC_SOFTWARE}
    ),
    Media.EBOOK: frozenset({Entity.EBOOK}),
    Media.ALL: frozenset(
        {
            Entity.MOVIE,
            Entity.ALBUM,
            Entity.ALL_ARTIST,
            Entity.PODCAST,
            Entity.MUSIC_VIDEO,
            Entity.MIX,
            Entity.AUDIOBOOK,
            Entity.TV_SEASON,
            Entity.ALL_TRACK,
        }
    ),
}
