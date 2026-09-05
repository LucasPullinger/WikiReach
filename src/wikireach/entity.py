# Wikidata entity models.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Entity:
    # A resolved Wikidata entity.

    id: str
    label: str
    description: str | None = None
