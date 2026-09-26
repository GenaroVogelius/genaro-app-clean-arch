from enum import StrEnum


class Explicitness(StrEnum):
    """RIAA parental advisory of a podcast or episode."""

    EXPLICIT = "explicit"
    CLEANED = "cleaned"
    NOT_EXPLICIT = "not_explicit"
