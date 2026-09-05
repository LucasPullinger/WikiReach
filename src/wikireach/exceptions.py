# Exceptions raised by WikiReach.


class WikiReachError(Exception):
    """Base exception for all WikiReach errors."""


class InvalidQueryError(WikiReachError):
    """Raised when a search query is invalid."""


class InvalidEntityIdError(WikiReachError):
    """Raised when an entity ID is invalid."""


class InvalidPropertyIdError(WikiReachError):
    """Raised when a Wikidata property ID is invalid."""


class InvalidDepthError(WikiReachError):
    """Raised when a traversal depth is invalid."""


class PathNotFoundError(WikiReachError):
    """Raised when no path exists within the requested depth."""


class EntityNotFoundError(WikiReachError):
    """Raised when an entity lookup returns no matching entity."""


class WikiReachHTTPError(WikiReachError):
    """Raised when a request to Wikidata fails."""


class WikiReachResponseError(WikiReachError):
    """Raised when Wikidata returns an unexpected response."""
