# Tests for the WikiReach client.

from decimal import Decimal
from typing import Any

import httpx
import pytest

from wikireach import (
    Claim,
    Connection,
    DateValue,
    Entity,
    EntityNotFoundError,
    EntityValue,
    InvalidDepthError,
    InvalidEntityIdError,
    InvalidPropertyIdError,
    InvalidQueryError,
    PathNotFoundError,
    PathResult,
    Property,
    QuantityValue,
    Relation,
    TraversalResult,
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


def claim(value: object) -> dict[str, object]:
    # Build a mocked Wikidata value claim.
    value_type = (
        "wikibase-entityid"
        if isinstance(value, dict) and value.get("entity-type") == "item"
        else "string"
    )
    return {
        "mainsnak": {
            "snaktype": "value",
            "datavalue": {"value": value, "type": value_type},
        }
    }


def mock_claims(
    monkeypatch: pytest.MonkeyPatch, claims: dict[str, list[object]]
) -> None:
    # Mock a wbgetentities response containing claims for Q937.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response(
            {"entities": {"Q937": {"claims": claims}}}
        ),
    )


def mock_relations_with_labels(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, list[object]],
    label_entities: dict[str, object],
    label_requests: list[str] | None = None,
) -> None:
    # Mock claims and label responses for relation resolution.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        params = kwargs["params"]
        if params["props"] == "claims":
            return json_response({"entities": {"Q937": {"claims": claims}}})

        assert params["props"] == "labels"
        if label_requests is not None:
            label_requests.append(params["ids"])
        requested_ids = params["ids"].split("|")
        return json_response(
            {
                "entities": {
                    entity_id: label_entities.get(entity_id, {"missing": ""})
                    for entity_id in requested_ids
                }
            }
        )

    monkeypatch.setattr(httpx, "get", mock_get)


def entity_record(label: str, description: str | None = None) -> dict[str, object]:
    # Build a mocked Wikidata entity record.
    record: dict[str, object] = {"labels": {"en": {"value": label}}}
    if description is not None:
        record["descriptions"] = {"en": {"value": description}}
    return record


def mock_neighbors(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, list[object]],
    target_entities: dict[str, object],
    entity_requests: list[list[str]] | None = None,
) -> None:
    # Mock claims and entity-resolution responses for neighbor lookup.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        params = kwargs["params"]
        if params["props"] == "claims":
            return json_response({"entities": {"Q937": {"claims": claims}}})

        assert params["props"] == "labels|descriptions"
        requested_ids = params["ids"].split("|")
        if entity_requests is not None:
            entity_requests.append(requested_ids)
        return json_response(
            {
                "entities": {
                    entity_id: target_entities.get(entity_id, {"missing": ""})
                    for entity_id in requested_ids
                }
            }
        )

    monkeypatch.setattr(httpx, "get", mock_get)


def mock_traversal(
    monkeypatch: pytest.MonkeyPatch,
    graph: dict[str, list[tuple[str, str]]],
    entity_records: dict[str, object],
    relation_requests: list[str] | None = None,
) -> None:
    # Mock a graph's claims and batched entity-resolution responses.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        params = kwargs["params"]
        if params["props"] == "claims":
            source_id = params["ids"]
            if relation_requests is not None:
                relation_requests.append(source_id)
            claims: dict[str, list[object]] = {}
            for property_id, target_id in graph.get(source_id, []):
                claims.setdefault(property_id, []).append(
                    claim({"entity-type": "item", "id": target_id})
                )
            return json_response({"entities": {source_id: {"claims": claims}}})

        assert params["props"] == "labels|descriptions"
        requested_ids = params["ids"].split("|")
        return json_response(
            {
                "entities": {
                    entity_id: entity_records.get(entity_id, {"missing": ""})
                    for entity_id in requested_ids
                }
            }
        )

    monkeypatch.setattr(httpx, "get", mock_get)


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
                                        "datavalue": {
                                            "value": {
                                                "id": "Q5",
                                                "entity-type": "item",
                                            },
                                            "type": "wikibase-entityid",
                                        },
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
        "P31": [Claim("P31", "Q937", EntityValue("Q5", "item"), "wikibase-entityid")],
        "P19": [Claim("P19", "Q937", {"id": "Q1731"}, "unknown")],
        "P106": [
            Claim("P106", "Q937", {"id": "Q169470"}, "unknown"),
            Claim("P106", "Q937", {"id": "Q901"}, "unknown"),
        ],
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

    assert WikiReach().claims("Q937") == {
        "P19": [Claim("P19", "Q937", None, snak_type)]
    }


def test_claims_convert_time_and_quantity_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Supported Wikidata datatypes become typed immutable value models.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response(
            {
                "entities": {
                    "Q937": {
                        "claims": {
                            "P569": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {
                                            "type": "time",
                                            "value": {
                                                "time": "+1879-03-14T00:00:00Z",
                                                "precision": 11,
                                            },
                                        },
                                    }
                                }
                            ],
                            "P2048": [
                                {
                                    "mainsnak": {
                                        "snaktype": "value",
                                        "datavalue": {
                                            "type": "quantity",
                                            "value": {"amount": "+42", "unit": "1"},
                                        },
                                    }
                                }
                            ],
                        }
                    }
                }
            }
        ),
    )

    claims = WikiReach().claims("Q937")

    assert claims["P569"][0].value == DateValue(1879, 3, 14, "day")
    assert claims["P2048"][0].value == QuantityValue(Decimal("42"))


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


def test_relations_returns_one_entity_relation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A single item-valued claim becomes a Relation.
    mock_claims(monkeypatch, {"P31": [claim({"entity-type": "item", "id": "Q5"})]})

    assert WikiReach().relations("Q937") == [Relation("P31", "Q937", "Q5")]


def test_relations_preserves_multiple_claims_for_one_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Multiple statements under one property remain separate relations.
    mock_claims(
        monkeypatch,
        {
            "P106": [
                claim({"entity-type": "item", "id": "Q169470"}),
                claim({"entity-type": "item", "id": "Q901"}),
            ]
        },
    )

    assert WikiReach().relations("Q937") == [
        Relation("P106", "Q937", "Q169470"),
        Relation("P106", "Q937", "Q901"),
    ]


def test_relations_spans_multiple_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    # Item-valued claims across properties become relations.
    mock_claims(
        monkeypatch,
        {
            "P31": [claim({"entity-type": "item", "id": "Q5"})],
            "P19": [claim({"entity-type": "item", "id": "Q1731"})],
        },
    )

    assert WikiReach().relations("Q937") == [
        Relation("P31", "Q937", "Q5"),
        Relation("P19", "Q937", "Q1731"),
    ]


def test_relations_ignores_non_entity_values(monkeypatch: pytest.MonkeyPatch) -> None:
    # Strings, dates, coordinates, URLs, and quantities do not become relations.
    mock_claims(
        monkeypatch,
        {
            "P31": [claim({"entity-type": "item", "id": "Q5"})],
            "P569": [claim({"time": "+1879-03-14T00:00:00Z"})],
            "P856": [claim("https://example.com")],
            "P2048": [claim({"amount": "+1"})],
        },
    )

    assert WikiReach().relations("Q937") == [Relation("P31", "Q937", "Q5")]


def test_relations_ignores_none_and_invalid_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-value snaks and malformed target IDs do not become relations.
    mock_claims(
        monkeypatch,
        {
            "P19": [
                {"mainsnak": {"snaktype": "novalue"}},
                claim({"entity-type": "item", "id": "not-a-q-id"}),
                claim({"entity-type": "item", "id": "P31"}),
            ]
        },
    )

    assert WikiReach().relations("Q937") == []


def test_relations_returns_empty_list_without_entity_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Claims without entity targets produce no relations.
    mock_claims(monkeypatch, {"P856": [claim("https://example.com")]})

    assert WikiReach().relations("Q937") == []


def test_relations_rejects_invalid_source_id() -> None:
    # Relation lookup reuses Q-ID validation through claims().
    with pytest.raises(InvalidEntityIdError):
        WikiReach().relations("P31")


def test_relations_are_unresolved_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # Existing calls retain ID-only relation results.
    mock_claims(monkeypatch, {"P31": [claim({"entity-type": "item", "id": "Q5"})]})

    assert WikiReach().relations("Q937") == [Relation("P31", "Q937", "Q5")]


def test_relations_resolve_source_property_and_target_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Opt-in resolution adds labels while retaining all original IDs.
    mock_relations_with_labels(
        monkeypatch,
        {"P31": [claim({"entity-type": "item", "id": "Q5"})]},
        {
            "Q937": {"labels": {"en": {"value": "Albert Einstein"}}},
            "P31": {"labels": {"en": {"value": "instance of"}}},
            "Q5": {"labels": {"en": {"value": "human"}}},
        },
    )

    assert WikiReach().relations("Q937", resolve_labels=True) == [
        Relation(
            property_id="P31",
            source_id="Q937",
            target_id="Q5",
            property_label="instance of",
            source_label="Albert Einstein",
            target_label="human",
        )
    ]


def test_relations_resolve_multiple_targets_in_one_unique_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Duplicate source and property IDs are requested only once.
    label_requests: list[str] = []
    mock_relations_with_labels(
        monkeypatch,
        {
            "P106": [
                claim({"entity-type": "item", "id": "Q169470"}),
                claim({"entity-type": "item", "id": "Q901"}),
                claim({"entity-type": "item", "id": "Q901"}),
            ]
        },
        {
            "Q937": {"labels": {"en": {"value": "Albert Einstein"}}},
            "P106": {"labels": {"en": {"value": "occupation"}}},
            "Q169470": {"labels": {"en": {"value": "physicist"}}},
            "Q901": {"labels": {"en": {"value": "scientist"}}},
        },
        label_requests,
    )

    relations = WikiReach().relations("Q937", resolve_labels=True)

    assert len(label_requests) == 1
    assert set(label_requests[0].split("|")) == {"Q937", "P106", "Q169470", "Q901"}
    assert [relation.target_label for relation in relations] == [
        "physicist",
        "scientist",
        "scientist",
    ]


def test_relations_keep_missing_english_labels_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Label resolution tolerates entities and properties without English labels.
    mock_relations_with_labels(
        monkeypatch,
        {"P31": [claim({"entity-type": "item", "id": "Q5"})]},
        {"Q937": {"labels": {}}, "P31": {"labels": {}}, "Q5": {"labels": {}}},
    )

    relation = WikiReach().relations("Q937", resolve_labels=True)[0]

    assert relation.property_label is None
    assert relation.source_label is None
    assert relation.target_label is None


def test_relations_reject_malformed_label_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Malformed label payloads retain the existing response-error model.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        if kwargs["params"]["props"] == "claims":
            return json_response(
                {
                    "entities": {
                        "Q937": {
                            "claims": {
                                "P31": [claim({"entity-type": "item", "id": "Q5"})]
                            }
                        }
                    }
                }
            )
        return json_response({"entities": {"Q937": {"labels": "invalid"}}})

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(WikiReachResponseError):
        WikiReach().relations("Q937", resolve_labels=True)


def test_relations_convert_label_http_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # HTTP failures during label resolution use the existing exception type.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        if kwargs["params"]["props"] == "claims":
            return json_response(
                {
                    "entities": {
                        "Q937": {
                            "claims": {
                                "P31": [claim({"entity-type": "item", "id": "Q5"})]
                            }
                        }
                    }
                }
            )
        return httpx.Response(503, request=httpx.Request("GET", args[0]))

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(WikiReachHTTPError):
        WikiReach().relations("Q937", resolve_labels=True)


def test_neighbors_returns_one_entity_with_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A relation target resolves to an Entity with its English metadata.
    mock_neighbors(
        monkeypatch,
        {"P31": [claim({"entity-type": "item", "id": "Q5"})]},
        {"Q5": entity_record("human", "common name for all humans")},
    )

    assert WikiReach().neighbors("Q937") == [
        Entity("Q5", "human", "common name for all humans")
    ]


def test_neighbors_return_none_without_an_english_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A target without an English description remains usable.
    mock_neighbors(
        monkeypatch,
        {"P31": [claim({"entity-type": "item", "id": "Q5"})]},
        {"Q5": {"labels": {"en": {"value": "human"}}, "descriptions": {}}},
    )

    assert WikiReach().neighbors("Q937") == [Entity("Q5", "human", None)]


def test_neighbors_fall_back_to_id_without_an_english_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A target without an English label remains available using its Q-ID.
    mock_neighbors(
        monkeypatch,
        {"P31": [claim({"entity-type": "item", "id": "Q5"})]},
        {"Q5": {"labels": {}, "descriptions": {}}},
    )

    assert WikiReach().neighbors("Q937") == [Entity("Q5", "Q5", None)]


def test_neighbors_preserve_first_seen_order_across_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Neighbor order follows the first appearance of targets in relation data.
    mock_neighbors(
        monkeypatch,
        {
            "P31": [claim({"entity-type": "item", "id": "Q5"})],
            "P19": [claim({"entity-type": "item", "id": "Q1731"})],
        },
        {"Q5": entity_record("human"), "Q1731": entity_record("Ulm")},
    )

    neighbors = WikiReach().neighbors("Q937")

    assert [entity.id for entity in neighbors] == ["Q5", "Q1731"]


def test_neighbors_deduplicate_target_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    # Repeated relation targets produce one neighbor and one requested ID.
    entity_requests: list[list[str]] = []
    mock_neighbors(
        monkeypatch,
        {
            "P106": [
                claim({"entity-type": "item", "id": "Q901"}),
                claim({"entity-type": "item", "id": "Q901"}),
            ]
        },
        {"Q901": entity_record("scientist")},
        entity_requests,
    )

    assert [entity.id for entity in WikiReach().neighbors("Q937")] == ["Q901"]
    assert entity_requests == [["Q901"]]


def test_neighbors_resolve_entities_in_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    # More than 50 targets are resolved in batches rather than per entity.
    target_ids = [f"Q{number}" for number in range(1, 52)]
    entity_requests: list[list[str]] = []
    mock_neighbors(
        monkeypatch,
        {
            "P31": [
                claim({"entity-type": "item", "id": target_id})
                for target_id in target_ids
            ]
        },
        {target_id: entity_record(target_id) for target_id in target_ids},
        entity_requests,
    )

    neighbors = WikiReach().neighbors("Q937")

    assert [entity.id for entity in neighbors] == target_ids
    assert [len(batch) for batch in entity_requests] == [50, 1]


def test_neighbors_ignore_missing_target_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing target records do not fail neighbor lookup.
    mock_neighbors(
        monkeypatch,
        {
            "P31": [claim({"entity-type": "item", "id": "Q5"})],
            "P19": [claim({"entity-type": "item", "id": "Q1731"})],
        },
        {"Q5": entity_record("human"), "Q1731": {"missing": ""}},
    )

    assert [entity.id for entity in WikiReach().neighbors("Q937")] == ["Q5"]


def test_neighbors_return_empty_list_when_no_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An entity without relations needs no entity-resolution request.
    mock_neighbors(monkeypatch, {}, {})

    assert WikiReach().neighbors("Q937") == []


def test_neighbors_reject_invalid_source_id() -> None:
    # Neighbor lookup reuses relation and claim Q-ID validation.
    with pytest.raises(InvalidEntityIdError):
        WikiReach().neighbors("P31")


def test_neighbors_convert_entity_resolution_http_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Failures after relation retrieval use the existing HTTP exception.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        if kwargs["params"]["props"] == "claims":
            return json_response(
                {
                    "entities": {
                        "Q937": {
                            "claims": {
                                "P31": [claim({"entity-type": "item", "id": "Q5"})]
                            }
                        }
                    }
                }
            )
        return httpx.Response(503, request=httpx.Request("GET", args[0]))

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(WikiReachHTTPError):
        WikiReach().neighbors("Q937")


def test_neighbors_reject_malformed_entity_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Invalid target entity payloads use the existing response exception.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        if kwargs["params"]["props"] == "claims":
            return json_response(
                {
                    "entities": {
                        "Q937": {
                            "claims": {
                                "P31": [claim({"entity-type": "item", "id": "Q5"})]
                            }
                        }
                    }
                }
            )
        return json_response({"entities": {"Q5": {"labels": "invalid"}}})

    monkeypatch.setattr(httpx, "get", mock_get)

    with pytest.raises(WikiReachResponseError):
        WikiReach().neighbors("Q937")


def test_traverse_depth_zero_returns_only_root(monkeypatch: pytest.MonkeyPatch) -> None:
    # Depth zero resolves the root without requesting its outgoing claims.
    relation_requests: list[str] = []
    mock_traversal(
        monkeypatch,
        {"Q1": [("P31", "Q2")]},
        {"Q1": entity_record("root"), "Q2": entity_record("target")},
        relation_requests,
    )

    result = WikiReach().traverse("Q1", depth=0)

    assert result == TraversalResult(Entity("Q1", "root"), (Entity("Q1", "root"),), ())
    assert relation_requests == []


def test_traverse_depth_one_discovers_direct_neighbors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Depth one includes direct targets and the root's outgoing relations.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P31", "Q2")]},
        {"Q1": entity_record("root"), "Q2": entity_record("target")},
    )

    result = WikiReach().traverse("Q1")

    assert [entity.id for entity in result.entities] == ["Q1", "Q2"]
    assert result.relations == (Relation("P31", "Q1", "Q2"),)


def test_traverse_depth_two_uses_stable_breadth_first_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Each level is discovered and expanded in breadth-first order.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P2", "Q3")],
            "Q2": [("P3", "Q4")],
            "Q3": [("P4", "Q5")],
        },
        {
            "Q1": entity_record("root"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
            "Q4": entity_record("four"),
            "Q5": entity_record("five"),
        },
    )

    result = WikiReach().traverse("Q1", depth=2)

    assert [entity.id for entity in result.entities] == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert [relation.source_id for relation in result.relations] == [
        "Q1",
        "Q1",
        "Q2",
        "Q3",
    ]


def test_traverse_prevents_cycles_and_preserves_duplicate_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Visited entities are not expanded twice, but duplicate statements remain.
    relation_requests: list[str] = []
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2"), ("P1", "Q2")], "Q2": [("P2", "Q1")]},
        {"Q1": entity_record("one"), "Q2": entity_record("two")},
        relation_requests,
    )

    result = WikiReach().traverse("Q1", depth=3)

    assert [entity.id for entity in result.entities] == ["Q1", "Q2"]
    assert len(result.relations) == 3
    assert relation_requests == ["Q1", "Q2"]


def test_traverse_deduplicates_entities_reached_by_multiple_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A target discovered via two sources appears once but both edges remain.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P2", "Q3")],
            "Q2": [("P3", "Q4")],
            "Q3": [("P4", "Q4")],
        },
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
            "Q4": entity_record("four"),
        },
    )

    result = WikiReach().traverse("Q1", depth=2)

    assert [entity.id for entity in result.entities] == ["Q1", "Q2", "Q3", "Q4"]
    assert [relation.target_id for relation in result.relations].count("Q4") == 2


def test_traverse_handles_entity_without_outgoing_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A leaf root produces an otherwise empty traversal result.
    mock_traversal(monkeypatch, {}, {"Q1": entity_record("root")})

    result = WikiReach().traverse("Q1", depth=2)

    assert result.entities == (Entity("Q1", "root"),)
    assert result.relations == ()


@pytest.mark.parametrize("depth", [-1, True])
def test_traverse_rejects_invalid_depth(depth: int) -> None:
    # Traversal depth must be a non-negative integer, excluding booleans.
    with pytest.raises(InvalidDepthError):
        WikiReach().traverse("Q1", depth=depth)


def test_traverse_rejects_invalid_root_id() -> None:
    # Root IDs use the shared Q-ID validation.
    with pytest.raises(InvalidEntityIdError):
        WikiReach().traverse("P31")


def test_traverse_ignores_missing_discovered_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing targets are omitted and never expanded at the next level.
    relation_requests: list[str] = []
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2")], "Q2": [("P2", "Q3")]},
        {"Q1": entity_record("root"), "Q2": {"missing": ""}},
        relation_requests,
    )

    result = WikiReach().traverse("Q1", depth=2)

    assert [entity.id for entity in result.entities] == ["Q1"]
    assert relation_requests == ["Q1"]


def test_traverse_converts_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # Root entity-resolution failures use the existing HTTP exception.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            503, request=httpx.Request("GET", args[0])
        ),
    )

    with pytest.raises(WikiReachHTTPError):
        WikiReach().traverse("Q1")


def test_traverse_rejects_malformed_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    # Malformed root entity data uses the existing response exception.
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: json_response({}))

    with pytest.raises(WikiReachResponseError):
        WikiReach().traverse("Q1")


def test_traverse_resolves_q937_root_label_with_language_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Multilingual labels returned as English fallbacks resolve the traversal root.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        params = kwargs["params"]
        assert params["languagefallback"] == "1"
        return json_response(
            {
                "entities": {
                    "Q937": {
                        "labels": {
                            "en": {
                                "language": "mul",
                                "for-language": "en",
                                "value": "Albert Einstein",
                            }
                        },
                        "descriptions": {},
                    }
                }
            }
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    assert WikiReach().traverse("Q937", depth=0).root.label == "Albert Einstein"


def test_path_finds_a_direct_relation(monkeypatch: pytest.MonkeyPatch) -> None:
    # A direct edge produces a one-relation path.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2")]},
        {"Q1": entity_record("one"), "Q2": entity_record("two")},
    )

    assert WikiReach().path("Q1", "Q2") == PathResult(
        (Entity("Q1", "one"), Entity("Q2", "two")),
        (Relation("P1", "Q1", "Q2"),),
    )


def test_path_finds_a_two_edge_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Parent pointers reconstruct paths longer than one edge.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2")], "Q2": [("P2", "Q3")]},
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
        },
    )

    result = WikiReach().path("Q1", "Q3")

    assert [entity.id for entity in result.entities] == ["Q1", "Q2", "Q3"]
    assert [relation.property_id for relation in result.relations] == ["P1", "P2"]


def test_path_chooses_shortest_and_first_discovered_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # BFS chooses a direct edge over longer paths and preserves relation ordering.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P2", "Q3"), ("P3", "Q4")],
            "Q2": [("P4", "Q4")],
            "Q3": [("P5", "Q4")],
        },
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
            "Q4": entity_record("four"),
        },
    )

    result = WikiReach().path("Q1", "Q4")

    assert [entity.id for entity in result.entities] == ["Q1", "Q4"]
    assert result.relations == (Relation("P3", "Q1", "Q4"),)


def test_path_chooses_first_equal_length_route(monkeypatch: pytest.MonkeyPatch) -> None:
    # The first relation-discovered parent wins when paths have equal length.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P2", "Q3")],
            "Q2": [("P3", "Q4")],
            "Q3": [("P4", "Q4")],
        },
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
            "Q4": entity_record("four"),
        },
    )

    assert [entity.id for entity in WikiReach().path("Q1", "Q4").entities] == [
        "Q1",
        "Q2",
        "Q4",
    ]


def test_path_handles_source_equal_to_target(monkeypatch: pytest.MonkeyPatch) -> None:
    # A zero-edge path resolves only its shared endpoint.
    mock_traversal(monkeypatch, {}, {"Q1": entity_record("one")})

    assert WikiReach().path("Q1", "Q1") == PathResult((Entity("Q1", "one"),), ())


def test_path_prevents_cycles_and_duplicate_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Visited IDs avoid cycles; duplicate edges do not replace the first parent.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P1", "Q2")],
            "Q2": [("P2", "Q1"), ("P3", "Q3")],
        },
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
        },
    )

    assert [entity.id for entity in WikiReach().path("Q1", "Q3").entities] == [
        "Q1",
        "Q2",
        "Q3",
    ]


@pytest.mark.parametrize("max_depth", [0, 1])
def test_path_respects_max_depth(
    monkeypatch: pytest.MonkeyPatch, max_depth: int
) -> None:
    # Targets beyond the permitted number of edges are not found.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2")], "Q2": [("P2", "Q3")]},
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
        },
    )

    with pytest.raises(PathNotFoundError):
        WikiReach().path("Q1", "Q3", max_depth=max_depth)


def test_path_reports_missing_target(monkeypatch: pytest.MonkeyPatch) -> None:
    # Exhausting the graph raises the dedicated path exception.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2")]},
        {"Q1": entity_record("one"), "Q2": entity_record("two")},
    )

    with pytest.raises(PathNotFoundError):
        WikiReach().path("Q1", "Q3")


@pytest.mark.parametrize("source_id,target_id", [("P31", "Q2"), ("Q1", "P31")])
def test_path_rejects_invalid_ids(source_id: str, target_id: str) -> None:
    # Both path endpoints require valid Q-IDs.
    with pytest.raises(InvalidEntityIdError):
        WikiReach().path(source_id, target_id)


@pytest.mark.parametrize("max_depth", [-1, True])
def test_path_rejects_invalid_max_depth(max_depth: int) -> None:
    # Maximum path depth follows traversal depth validation rules.
    with pytest.raises(InvalidDepthError):
        WikiReach().path("Q1", "Q2", max_depth=max_depth)


def test_path_rejects_missing_final_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    # A path cannot be returned with an unresolved final endpoint.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q2")]},
        {"Q1": entity_record("one"), "Q2": {"missing": ""}},
    )

    with pytest.raises(EntityNotFoundError):
        WikiReach().path("Q1", "Q2")


def test_path_converts_http_and_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Existing HTTP and response errors propagate through path search.
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: json_response({}))

    with pytest.raises(WikiReachResponseError):
        WikiReach().path("Q1", "Q2")


def test_relations_filter_one_or_multiple_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Filters retain only the requested property IDs in source order.
    mock_claims(
        monkeypatch,
        {
            "P31": [claim({"entity-type": "item", "id": "Q5"})],
            "P19": [claim({"entity-type": "item", "id": "Q1731"})],
            "P106": [claim({"entity-type": "item", "id": "Q901"})],
        },
    )

    assert [
        relation.property_id
        for relation in WikiReach().relations("Q937", properties={"P19", "P106"})
    ] == ["P19", "P106"]


def test_relations_filter_no_matches_and_empty_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Empty and non-matching filters yield no outgoing relations.
    mock_claims(
        monkeypatch,
        {"P31": [claim({"entity-type": "item", "id": "Q5"})]},
    )

    assert WikiReach().relations("Q937", properties={"P19"}) == []
    assert WikiReach().relations("Q937", properties=[]) == []


def test_relations_none_and_duplicate_properties_preserve_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # None means unfiltered, and duplicate requested IDs do not change results.
    mock_claims(
        monkeypatch,
        {
            "P31": [claim({"entity-type": "item", "id": "Q5"})],
            "P19": [claim({"entity-type": "item", "id": "Q1731"})],
        },
    )

    unfiltered = WikiReach().relations("Q937")
    filtered = WikiReach().relations("Q937", properties=["P31", "P31"])

    assert [relation.property_id for relation in unfiltered] == ["P31", "P19"]
    assert [relation.property_id for relation in filtered] == ["P31"]


@pytest.mark.parametrize("properties", [{"31"}, {"Q31"}, {"PABC"}, {""}])
def test_graph_operations_reject_invalid_property_ids(
    properties: set[str],
) -> None:
    # Every graph operation validates supplied Wikidata property IDs.
    wiki = WikiReach()
    with pytest.raises(InvalidPropertyIdError):
        wiki.relations("Q1", properties=properties)
    with pytest.raises(InvalidPropertyIdError):
        wiki.neighbors("Q1", properties=properties)
    with pytest.raises(InvalidPropertyIdError):
        wiki.traverse("Q1", properties=properties)
    with pytest.raises(InvalidPropertyIdError):
        wiki.path("Q1", "Q2", properties=properties)


def test_neighbors_apply_property_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    # Neighbor resolution sees only targets from allowed edge types.
    mock_neighbors(
        monkeypatch,
        {
            "P19": [claim({"entity-type": "item", "id": "Q1731"})],
            "P106": [claim({"entity-type": "item", "id": "Q901"})],
        },
        {"Q1731": entity_record("Ulm"), "Q901": entity_record("scientist")},
    )

    assert [
        entity.id for entity in WikiReach().neighbors("Q937", properties={"P19"})
    ] == ["Q1731"]


def test_traverse_filters_before_expanding_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Excluded first-hop targets are never added to the traversal frontier.
    relation_requests: list[str] = []
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P2", "Q3")],
            "Q2": [("P1", "Q4")],
            "Q3": [("P2", "Q5")],
        },
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
            "Q4": entity_record("four"),
            "Q5": entity_record("five"),
        },
        relation_requests,
    )

    result = WikiReach().traverse("Q1", depth=2, properties={"P1"})

    assert [entity.id for entity in result.entities] == ["Q1", "Q2", "Q4"]
    assert relation_requests == ["Q1", "Q2"]


def test_path_filters_before_searching_excluded_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A path follows only allowed edge types and skips excluded frontier nodes.
    relation_requests: list[str] = []
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q2"), ("P2", "Q3")],
            "Q2": [("P1", "Q4")],
            "Q3": [("P2", "Q4")],
        },
        {
            "Q1": entity_record("one"),
            "Q2": entity_record("two"),
            "Q3": entity_record("three"),
            "Q4": entity_record("four"),
        },
        relation_requests,
    )

    result = WikiReach().path("Q1", "Q4", properties={"P1"})

    assert [entity.id for entity in result.entities] == ["Q1", "Q2", "Q4"]
    assert relation_requests == ["Q1", "Q2"]


def test_connections_return_one_shared_target(monkeypatch: pytest.MonkeyPatch) -> None:
    # A target referenced by both sources becomes a Connection.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q3")], "Q2": [("P2", "Q3")]},
        {"Q3": entity_record("shared")},
    )

    assert WikiReach().connections("Q1", "Q2") == [
        Connection(
            Entity("Q3", "shared"),
            (Relation("P1", "Q1", "Q3"),),
            (Relation("P2", "Q2", "Q3"),),
        )
    ]


def test_connections_preserve_left_order_and_multiple_shared_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Shared targets follow their first appearance in the left source relations.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q4"), ("P2", "Q3"), ("P3", "Q5")],
            "Q2": [("P4", "Q3"), ("P5", "Q4")],
        },
        {"Q3": entity_record("three"), "Q4": entity_record("four")},
    )

    connections = WikiReach().connections("Q1", "Q2")

    assert [connection.entity.id for connection in connections] == ["Q4", "Q3"]


def test_connections_preserve_all_relations_for_each_shared_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Duplicate and multi-property statements remain available as explanations.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q3"), ("P1", "Q3"), ("P2", "Q3")],
            "Q2": [("P4", "Q3"), ("P5", "Q3")],
        },
        {"Q3": entity_record("shared")},
    )

    connection = WikiReach().connections("Q1", "Q2")[0]

    assert [relation.property_id for relation in connection.left_relations] == [
        "P1",
        "P1",
        "P2",
    ]
    assert [relation.property_id for relation in connection.right_relations] == [
        "P4",
        "P5",
    ]


def test_connections_return_empty_for_no_shared_or_allowed_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No intersection and an empty filter both produce no connections.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q3")], "Q2": [("P2", "Q4")]},
        {"Q3": entity_record("three"), "Q4": entity_record("four")},
    )

    assert WikiReach().connections("Q1", "Q2") == []
    assert WikiReach().connections("Q1", "Q2", properties=[]) == []


def test_connections_apply_property_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only shared targets reached through allowed properties are retained.
    mock_traversal(
        monkeypatch,
        {
            "Q1": [("P1", "Q3"), ("P2", "Q4")],
            "Q2": [("P1", "Q3"), ("P2", "Q4")],
        },
        {"Q3": entity_record("three"), "Q4": entity_record("four")},
    )

    assert [
        connection.entity.id
        for connection in WikiReach().connections("Q1", "Q2", properties={"P2"})
    ] == ["Q4"]


@pytest.mark.parametrize("left_id,right_id", [("P1", "Q2"), ("Q1", "P2")])
def test_connections_reject_invalid_source_ids(left_id: str, right_id: str) -> None:
    # Both connection sources require valid Q-IDs.
    with pytest.raises(InvalidEntityIdError):
        WikiReach().connections(left_id, right_id)


def test_connections_reject_invalid_property_ids() -> None:
    # Connection filters use the shared property-ID validation.
    with pytest.raises(InvalidPropertyIdError):
        WikiReach().connections("Q1", "Q2", properties={"Q31"})


def test_connections_skip_missing_shared_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Shared targets that no longer exist are omitted from the result.
    mock_traversal(
        monkeypatch,
        {"Q1": [("P1", "Q3")], "Q2": [("P2", "Q3")]},
        {"Q3": {"missing": ""}},
    )

    assert WikiReach().connections("Q1", "Q2") == []


def test_connections_convert_http_and_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Existing HTTP and malformed-response exceptions propagate unchanged.
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: json_response({}))

    with pytest.raises(WikiReachResponseError):
        WikiReach().connections("Q1", "Q2")


def test_connections_convert_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    # HTTP failures while retrieving either source propagate unchanged.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(
            503, request=httpx.Request("GET", args[0])
        ),
    )

    with pytest.raises(WikiReachHTTPError):
        WikiReach().connections("Q1", "Q2")


def test_property_returns_english_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    # Property lookup returns typed metadata without exposing raw API data.
    def mock_get(*args: Any, **kwargs: Any) -> httpx.Response:
        params = kwargs["params"]
        assert params["ids"] == "P31"
        assert params["props"] == "labels|descriptions|datatype"
        return json_response(
            {
                "entities": {
                    "P31": {
                        "labels": {"en": {"value": "instance of"}},
                        "descriptions": {"en": {"value": "class membership"}},
                        "datatype": "wikibase-item",
                    }
                }
            }
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    assert WikiReach().property("P31") == Property(
        "P31", "instance of", "class membership", "wikibase-item"
    )


@pytest.mark.parametrize("property_id", ["", "31", "Q31", "PABC"])
def test_property_rejects_invalid_ids(property_id: str) -> None:
    # Property lookup uses the existing P-ID validation exception.
    with pytest.raises(InvalidPropertyIdError):
        WikiReach().property(property_id)


def test_property_rejects_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    # Missing required property metadata raises a WikiReach response error.
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: json_response({"entities": {"P31": {}}}),
    )

    with pytest.raises(WikiReachResponseError):
        WikiReach().property("P31")
