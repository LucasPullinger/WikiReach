# Wikidata entity models.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Entity:
    # A Wikidata entity returned by a search.

    id: str
    label: str
    description: str | None = None
