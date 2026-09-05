# Wikidata entity relationship models.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Relation:
    # A directed relationship between two Wikidata entities.

    property_id: str
    source_id: str
    target_id: str
    property_label: str | None = None
    source_label: str | None = None
    target_label: str | None = None
