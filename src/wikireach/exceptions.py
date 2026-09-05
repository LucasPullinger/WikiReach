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


class EntityNotFoundError(WikiReachError):
    # Raised when a search returns no matching entities.
    pass


class WikiReachHTTPError(WikiReachError):
    # Raised when a request to Wikidata fails.
    pass


class WikiReachResponseError(WikiReachError):
    # Raised when Wikidata returns an unexpected response.
    pass
