class ExternalServiceError(Exception):
    """An external data source failed or returned an unusable response."""


class PodcastNotFoundError(Exception):
    """No result exists for the requested podcast id."""


class NotAPodcastError(Exception):
    """The requested id exists but does not refer to a podcast."""


class PodcastPersistenceError(Exception):
    """The podcast could not be persisted."""


class ArtworkUnavailableError(Exception):
    """The artwork of a podcast could not be downloaded, processed or stored."""
