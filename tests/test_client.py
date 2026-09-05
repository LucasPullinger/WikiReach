# Tests for the WikiReach client.

from typing import Any

import httpx
import pytest

from wikireach import (
    EntityNotFoundError,
    InvalidQueryError,
    WikiReach,
    WikiReachHTTPError,
    WikiReachResponseError,
)


def json_response(payload: object) -> httpx.Response:
    # Build a successful mocked Wikidata response.
    return httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", "https://www.wikidata.org/w/api.php"),
    )


def test_search_returns_best_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    # A search returns the first entity from Wikidata.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("GET", args[0], params=kwargs["params"])
        assert request.url.params["search"] == "Albert Einstein"
        assert kwargs["headers"]["User-Agent"].startswith("WikiReach/")
        return httpx.Response(
            200,
            json={
                "search": [
                    {
                        "id": "Q937",
                        "label": "Albert Einstein",
                        "description": "German-born theoretical physicist",
                    }
                ]
            },
            request=request,
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    entity = WikiReach().search("Albert Einstein")

    assert entity.id == "Q937"
    assert entity.label == "Albert Einstein"
    assert entity.description == "German-born theoretical physicist"


def test_search_rejects_empty_query() -> None:
    # Blank search queries fail before a request is made.
    with pytest.raises(InvalidQueryError, match="must not be empty"):
        WikiReach().search("  ")


def test_search_raises_when_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty search response raises a clear exception.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response({"search": []}),
    )

    with pytest.raises(EntityNotFoundError, match="No Wikidata entity"):
        WikiReach().search("not-a-real-entity")


def test_search_converts_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # HTTP failures are exposed as WikiReach errors.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("GET", args[0])
        return httpx.Response(503, request=request)

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(WikiReachHTTPError, match="Could not retrieve"):
        WikiReach().search("Albert Einstein")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"search": [{"id": "Q937"}]},
        {"search": ["not an entity"]},
    ],
)
def test_search_rejects_invalid_response(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    # Malformed API payloads are exposed as WikiReach errors.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response(payload),
    )

    with pytest.raises(WikiReachResponseError):
        WikiReach().search("Albert Einstein")
