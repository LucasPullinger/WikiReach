# Wikidata traversal result models.

from dataclasses import dataclass

from .entity import Entity
from .relation import Relation


@dataclass(frozen=True, slots=True)
class TraversalResult:
    # The entities and relations discovered by an outward traversal.

    root: Entity
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]
