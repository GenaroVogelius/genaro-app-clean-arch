class PodcastNotFoundError(Exception):
    """No result exists for the requested podcast id."""


class NotAPodcastError(Exception):
    """The requested id exists but does not refer to a podcast."""


class PodcastPersistenceError(Exception):
    """The podcast could not be persisted."""


class PodcastRetrievalError(Exception):
    """The stored podcasts could not be read."""
