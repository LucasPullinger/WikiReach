# Synchronous client for the Wikidata API.

import httpx

from .entity import Entity
from .exceptions import (
    EntityNotFoundError,
    InvalidQueryError,
    WikiReachHTTPError,
    WikiReachResponseError,
)


class WikiReach:
    # Search for entities using the Wikidata API.

    _API_URL = "https://www.wikidata.org/w/api.php"
    _USER_AGENT = "WikiReach/0.1.0 (https://github.com/wikireach/wikireach)"

    def search(self, query: str) -> Entity:
        # Return the best English Wikidata entity matching the query.
        if not query.strip():
            raise InvalidQueryError("Search query must not be empty.")

        try:
            response = httpx.get(
                self._API_URL,
                params={
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "format": "json",
                },
                headers={"User-Agent": self._USER_AGENT},
                timeout=10.0,
            )
            response.raise_for_status()
            payload: object = response.json()
        except httpx.HTTPError as error:
            raise WikiReachHTTPError(
                "Could not retrieve results from Wikidata."
            ) from error
        except ValueError as error:
            raise WikiReachResponseError("Wikidata returned invalid JSON.") from error

        return self._entity_from_payload(payload)

    @staticmethod
    def _entity_from_payload(payload: object) -> Entity:
        if not isinstance(payload, dict):
            raise WikiReachResponseError("Wikidata returned an invalid response.")

        results = payload.get("search")
        if not isinstance(results, list):
            raise WikiReachResponseError("Wikidata response is missing search results.")
        if not results:
            raise EntityNotFoundError("No Wikidata entity found for the search query.")

        result = results[0]
        if not isinstance(result, dict):
            raise WikiReachResponseError("Wikidata returned an invalid search result.")

        entity_id = result.get("id")
        label = result.get("label")
        description = result.get("description")
        if not isinstance(entity_id, str) or not isinstance(label, str):
            raise WikiReachResponseError(
                "Wikidata search result is missing entity data."
            )
        if description is not None and not isinstance(description, str):
            raise WikiReachResponseError(
                "Wikidata search result has an invalid description."
            )

        return Entity(id=entity_id, label=label, description=description)
