class BeaverChoiceError(Exception):
    """Base exception for Beaver's Choice domain errors."""


class UnknownCatalogItemError(BeaverChoiceError):
    """Raised when a domain service receives an unknown catalog item."""


class InvalidDateError(BeaverChoiceError, ValueError):
    """Raised when a date value is not in the expected ISO format."""

