# Tests for the WikiReach client.

from typing import Any

import httpx
import pytest

from wikireach import (
    EntityNotFoundError,
    InvalidEntityIdError,
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


def test_entity_returns_requested_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    # A Q-ID lookup returns the requested entity's English metadata.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("GET", args[0], params=kwargs["params"])
        assert request.url.params["action"] == "wbgetentities"
        assert request.url.params["ids"] == "Q937"
        assert request.url.params["languages"] == "en"
        assert request.url.params["props"] == "labels|descriptions"
        return httpx.Response(
            200,
            json={
                "entities": {
                    "Q937": {
                        "labels": {"en": {"value": "Albert Einstein"}},
                        "descriptions": {
                            "en": {"value": "German-born theoretical physicist"}
                        },
                    }
                }
            },
            request=request,
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    entity = WikiReach().entity("Q937")

    assert entity.id == "Q937"
    assert entity.label == "Albert Einstein"
    assert entity.description == "German-born theoretical physicist"


@pytest.mark.parametrize("entity_id", ["", "937", "P31", "QABC", "Q 937"])
def test_entity_rejects_invalid_ids(entity_id: str) -> None:
    # Invalid Q-ID formats fail before a request is made.
    with pytest.raises(InvalidEntityIdError, match="must be a Wikidata Q-ID"):
        WikiReach().entity(entity_id)


def test_entity_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # A missing Wikidata entity raises a clear exception.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response(
            {"entities": {"Q999999999": {"missing": ""}}}
        ),
    )

    with pytest.raises(EntityNotFoundError, match="Q999999999"):
        WikiReach().entity("Q999999999")


def test_entity_converts_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # HTTP failures are exposed as WikiReach errors.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        return httpx.Response(500, request=httpx.Request("GET", args[0]))

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(WikiReachHTTPError, match="Could not retrieve"):
        WikiReach().entity("Q937")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"entities": {"Q937": {}}},
        {"entities": {"Q937": {"labels": {"en": {}}}}},
    ],
)
def test_entity_rejects_invalid_response(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    # Malformed lookup payloads are exposed as WikiReach errors.
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: json_response(payload))

    with pytest.raises(WikiReachResponseError):
        WikiReach().entity("Q937")


def test_claims_returns_multiple_properties_and_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Claims preserve raw main-snak values under their property IDs.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        request = httpx.Request("GET", args[0], params=kwargs["params"])
        assert request.url.params["action"] == "wbgetentities"
        assert request.url.params["ids"] == "Q937"
        assert request.url.params["props"] == "claims"
        return httpx.Response(
            200,
            json={
                "entities": {
                    "Q937": {
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {"value": {"id": "Q5"}},
                                    }
                                }
                            ],
                            "P19": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {"value": {"id": "Q1731"}},
                                    }
                                }
                            ],
                            "P106": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {"value": {"id": "Q169470"}},
                                    }
                                },
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {"value": {"id": "Q901"}},
                                    }
                                },
                            ],
                        }
                    }
                }
            },
            request=request,
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    assert WikiReach().claims("Q937") == {
        "P31": [{"id": "Q5"}],
        "P19": [{"id": "Q1731"}],
        "P106": [{"id": "Q169470"}, {"id": "Q901"}],
    }


@pytest.mark.parametrize("snak_type", ["somevalue", "novalue"])
def test_claims_represent_non_value_snaks_as_none(
    monkeypatch: pytest.MonkeyPatch, snak_type: str
) -> None:
    # Valid snaks without a data value remain represented in the result.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response(
            {
                "entities": {
                    "Q937": {"claims": {"P19": [{"mainsnak": {"snaktype": snak_type}}]}}
                }
            }
        ),
    )

    assert WikiReach().claims("Q937") == {"P19": [None]}


def test_claims_returns_empty_mapping_for_entity_without_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An entity with no claims returns an empty mapping.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response({"entities": {"Q937": {"claims": {}}}}),
    )

    assert WikiReach().claims("Q937") == {}


def test_claims_rejects_invalid_id() -> None:
    # Claim retrieval uses the shared Q-ID validation.
    with pytest.raises(InvalidEntityIdError):
        WikiReach().claims("P31")


def test_claims_raises_when_entity_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A missing entity raises the existing not-found exception.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response({"entities": {"Q937": {"missing": ""}}}),
    )

    with pytest.raises(EntityNotFoundError):
        WikiReach().claims("Q937")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"entities": {"Q937": {}}},
        {"entities": {"Q937": {"claims": {"P31": [{}]}}}},
    ],
)
def test_claims_rejects_malformed_response(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    # Malformed claims responses raise a WikiReach-specific exception.
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: json_response(payload))

    with pytest.raises(WikiReachResponseError):
        WikiReach().claims("Q937")


def test_claims_converts_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # HTTP failures are exposed as WikiReach errors.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            500, request=httpx.Request("GET", "https://www.wikidata.org/w/api.php")
        ),
    )

    with pytest.raises(WikiReachHTTPError):
        WikiReach().claims("Q937")
