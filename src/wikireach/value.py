"""Typed Wikidata claim value models."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EntityValue:
    """A Wikidata entity reference used as a claim value."""

    id: str
    entity_type: str


@dataclass(frozen=True, slots=True)
class DateValue:
    """A Wikidata date value."""

    year: int
    month: int
    day: int
    precision: str
    calendar_model: str | None = None


@dataclass(frozen=True, slots=True)
class QuantityValue:
    """A Wikidata quantity value."""

    amount: Decimal
    unit: str | None = None
