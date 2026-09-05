# Wikidata path result models.

from dataclasses import dataclass

from .entity import Entity
from .relation import Relation


@dataclass(frozen=True, slots=True)
class PathResult:
    # The ordered entities and relations that form a graph path.

    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
