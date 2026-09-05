# Synchronous client for the Wikidata API.

import re

import httpx

from .entity import Entity
from .exceptions import (
    EntityNotFoundError,
    InvalidEntityIdError,
    InvalidQueryError,
    WikiReachHTTPError,
    WikiReachResponseError,
)


class WikiReach:
    # Search for entities using the Wikidata API.

    _API_URL = "https://www.wikidata.org/w/api.php"
    _USER_AGENT = "WikiReach/0.1.0 (https://github.com/wikireach/wikireach)"
    _ENTITY_ID_PATTERN = re.compile(r"Q[1-9]\d*$")

    def search(self, query: str) -> Entity:
        # Return the best English Wikidata entity matching the query.
        if not query.strip():
            raise InvalidQueryError("Search query must not be empty.")

        return self._entity_from_search_payload(
            self._get_payload(
                {
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "format": "json",
                }
            )
        )

    def entity(self, entity_id: str) -> Entity:
        # Return an English Wikidata entity for a Q-ID.
        if not isinstance(entity_id, str) or not self._ENTITY_ID_PATTERN.fullmatch(
            entity_id
        ):
            raise InvalidEntityIdError(
                "Entity ID must be a Wikidata Q-ID such as 'Q937'."
            )

        return self._entity_from_lookup_payload(
            self._get_payload(
                {
                    "action": "wbgetentities",
                    "ids": entity_id,
                    "languages": "en",
                    "props": "labels|descriptions",
                    "format": "json",
                }
            ),
            entity_id,
        )

    def _get_payload(self, params: dict[str, str]) -> object:
        # Request and decode a Wikidata API response.
        try:
            response = httpx.get(
                self._API_URL,
                params=params,
                headers={"User-Agent": self._USER_AGENT},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as error:
            raise WikiReachHTTPError(
                "Could not retrieve results from Wikidata."
            ) from error
        except ValueError as error:
            raise WikiReachResponseError("Wikidata returned invalid JSON.") from error

    @staticmethod
    def _entity_from_search_payload(payload: object) -> Entity:
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

    @staticmethod
    def _entity_from_lookup_payload(payload: object, entity_id: str) -> Entity:
        # Convert a wbgetentities response into an Entity.
        if not isinstance(payload, dict):
            raise WikiReachResponseError("Wikidata returned an invalid response.")

        entities = payload.get("entities")
        if not isinstance(entities, dict):
            raise WikiReachResponseError("Wikidata response is missing entities.")
        result = entities.get(entity_id)
        if not isinstance(result, dict):
            raise WikiReachResponseError("Wikidata response is missing entity data.")
        if "missing" in result:
            raise EntityNotFoundError(f"Wikidata entity {entity_id} was not found.")

        label = WikiReach._localized_value(result.get("labels"), "label")
        description_data = result.get("descriptions")
        description = (
            None
            if description_data is None
            else WikiReach._localized_value(description_data, "description")
        )
        return Entity(id=entity_id, label=label, description=description)

    @staticmethod
    def _localized_value(data: object, field: str) -> str:
        # Extract an English label or description from an API field.
        if not isinstance(data, dict):
            raise WikiReachResponseError(f"Wikidata entity has an invalid {field}.")
        english = data.get("en")
        if not isinstance(english, dict):
            raise WikiReachResponseError(
                f"Wikidata entity is missing an English {field}."
            )
        value = english.get("value")
        if not isinstance(value, str):
            raise WikiReachResponseError(f"Wikidata entity has an invalid {field}.")
        return value
