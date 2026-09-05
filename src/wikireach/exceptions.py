# Exceptions raised by WikiReach.


class WikiReachError(Exception):
    # Base exception for WikiReach errors.
    pass


class InvalidQueryError(WikiReachError):
    # Raised when a search query is invalid.
    pass


class InvalidEntityIdError(WikiReachError):
    # Raised when an entity ID is invalid.
    pass


class InvalidDepthError(WikiReachError):
    # Raised when a traversal depth is invalid.
    pass


class PathNotFoundError(WikiReachError):
    # Raised when no path exists within the requested depth.
    pass


class EntityNotFoundError(WikiReachError):
    # Raised when a search returns no matching entities.
    pass


class WikiReachHTTPError(WikiReachError):
    # Raised when a request to Wikidata fails.
    pass


class WikiReachResponseError(WikiReachError):
    # Raised when Wikidata returns an unexpected response.
    pass
