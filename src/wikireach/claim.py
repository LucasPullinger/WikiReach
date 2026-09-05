# Typed Wikidata claim models.

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias

QualifierValues: TypeAlias = Mapping[str, tuple[object, ...]]
Reference: TypeAlias = Mapping[str, tuple[object, ...]]
References: TypeAlias = tuple[Reference, ...]


# Create a fresh immutable default for claims without qualifiers.
def _empty_qualifiers() -> QualifierValues:
    return MappingProxyType({})


# Create a fresh immutable default for claims without references.
def _empty_references() -> References:
    return ()


@dataclass(frozen=True, slots=True)
class Claim:
    # A Wikidata statement with values, context, rank, identity, and sources.

    property_id: str
    source_id: str
    value: object
    value_type: str
    qualifiers: QualifierValues = field(default_factory=_empty_qualifiers)
    rank: str = "normal"
    statement_id: str | None = None
    references: References = field(default_factory=_empty_references)
