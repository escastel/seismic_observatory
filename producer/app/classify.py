"""Sorting of the items of a USGS response (spec 003, FR-003, FR-010, FR-011).

Every item ends in exactly one list, so received = earthquakes + excluded,
where "excluded" counts both other event types and unidentifiable items:

- earthquakes:     id, readable updated and properties.type == "earthquake"
- excluded:        identifiable, other type (not_earthquake) or no type (missing_type)
- unidentifiable:  not an object, no id, or no readable updated; they cannot be
                   stored as exclusions nor published, and are described in the
                   extraction's error_detail
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

EARTHQUAKE = "earthquake"


@dataclass(frozen=True)
class Item:
    position: int                 # index in the response's features list
    event_id: str
    updated_at: datetime
    event_type: str | None
    feature: dict[str, Any]


@dataclass(frozen=True)
class Excluded:
    item: Item
    reason_code: str              # not_earthquake | missing_type


@dataclass(frozen=True)
class Unidentifiable:
    position: int
    reason: str


@dataclass(frozen=True)
class Classified:
    earthquakes: list[Item]
    excluded: list[Excluded]
    unidentifiable: list[Unidentifiable]

    @property
    def received(self) -> int:
        return len(self.earthquakes) + len(self.excluded) + len(self.unidentifiable)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded) + len(self.unidentifiable)

    def unidentifiable_detail(self) -> str | None:
        """Text for extraction.error_detail, or None when every item was identifiable."""
        if not self.unidentifiable:
            return None
        listed = "; ".join(f"#{item.position}: {item.reason}" for item in self.unidentifiable[:20])
        more = "" if len(self.unidentifiable) <= 20 else f"; and {len(self.unidentifiable) - 20} more"
        return f"{len(self.unidentifiable)} unidentifiable item(s) counted as excluded ({listed}{more})"


def millis_to_utc(value: Any) -> datetime | None:
    """USGS milliseconds since the Unix epoch as an aware UTC datetime."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def classify(features: Sequence[Any]) -> Classified:
    earthquakes: list[Item] = []
    excluded: list[Excluded] = []
    unidentifiable: list[Unidentifiable] = []
    for position, feature in enumerate(features):
        if not isinstance(feature, dict):
            unidentifiable.append(Unidentifiable(position, f"not an object ({type(feature).__name__})"))
            continue
        event_id = feature.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            unidentifiable.append(Unidentifiable(position, "no id"))
            continue
        properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        updated_at = millis_to_utc(properties.get("updated"))
        if updated_at is None:
            unidentifiable.append(Unidentifiable(position, f"id {event_id}: no readable 'updated'"))
            continue
        event_type = properties.get("type")
        item = Item(position, event_id.strip(), updated_at, event_type if isinstance(event_type, str) else None, feature)
        if item.event_type == EARTHQUAKE:
            earthquakes.append(item)
        elif item.event_type is None:
            excluded.append(Excluded(item, "missing_type"))
        else:
            excluded.append(Excluded(item, "not_earthquake"))
    return Classified(earthquakes, excluded, unidentifiable)
