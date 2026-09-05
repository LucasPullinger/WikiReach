# Typed Wikidata claim models.

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias

QualifierValues: TypeAlias = Mapping[str, tuple[object, ...]]


# Create a fresh immutable default for claims without qualifiers.
def _empty_qualifiers() -> QualifierValues:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class Claim:
    # A Wikidata claim with a typed main value and optional qualifier values.

    property_id: str
    source_id: str
    value: object
    value_type: str
    qualifiers: QualifierValues = field(default_factory=_empty_qualifiers)
