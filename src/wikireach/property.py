# Wikidata property metadata models.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Property:
    # A resolved Wikidata property and its English metadata.

    id: str
    label: str | None
    description: str | None
    datatype: str
