# Wikidata direct-connection result models.

from dataclasses import dataclass

from .entity import Entity
from .relation import Relation


@dataclass(frozen=True, slots=True)
class Connection:
    # A shared target and the relations that connect two source entities to it.

    entity: Entity
    left_relations: tuple[Relation, ...]
    right_relations: tuple[Relation, ...]
