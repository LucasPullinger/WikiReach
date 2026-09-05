# Private HTTP access for the Wikidata API.

import httpx

from .exceptions import WikiReachHTTPError, WikiReachResponseError

API_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "WikiReach/0.1.0 (https://github.com/wikireach/wikireach)"
TIMEOUT_SECONDS = 10.0
BATCH_SIZE = 50


def get_payload(params: dict[str, str]) -> object:
    # Request and decode a Wikidata API response.
    try:
        response = httpx.get(
            API_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise WikiReachHTTPError("Could not retrieve results from Wikidata.") from error
    except ValueError as error:
        raise WikiReachResponseError("Wikidata returned invalid JSON.") from error
