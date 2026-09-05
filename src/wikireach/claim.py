# Typed Wikidata claim models.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Claim:
    # A Wikidata claim with its raw value and Wikidata value type.

    property_id: str
    source_id: str
    value: object
    value_type: str
