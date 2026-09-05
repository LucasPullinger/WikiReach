# Tests for the WikiReach client.

from typing import Any

import httpx
import pytest

from wikireach import (
    Entity,
    EntityNotFoundError,
    InvalidEntityIdError,
    InvalidQueryError,
    Relation,
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
    return {"mainsnak": {"snaktype": "value", "datavalue": {"value": value}}}


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
