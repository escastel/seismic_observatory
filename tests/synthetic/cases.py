"""Synthetic messages damaged on purpose (specs/004-consumer-quality/contracts/reprocess.md).

One case per rule of the catalog plus the acceptance cases. Every message carries
"synthetic": true and "synthetic_case"; events use the reserved id synthetic-<case>.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

PREFIX = "synthetic-"
BATCH_PREFIX = "synthetic-batch-"
DROP = object()

QUARANTINE, EXCLUSION, EVENT = "quarantine", "exclusion", "event"


@dataclass(frozen=True)
class SyntheticCase:
    case: str
    description: str
    message: dict[str, Any] | list | bytes
    outcome: str  # quarantine | exclusion | event
    codes: tuple[str, ...]  # reasons, exclusion reason or flags
    rules_outcome: str | None = None  # what rules.evaluate says when it differs (model rejection)
    country: str | None = None  # expected country for events, None when none

    @property
    def event_id(self) -> str:
        return PREFIX + self.case

    def raw(self) -> bytes:
        return self.message if isinstance(self.message, bytes) else json.dumps(self.message).encode()

    @property
    def expected_at_rules(self) -> str:
        return self.rules_outcome or self.outcome


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def base(case: str, now: datetime, **changes: Any) -> dict[str, Any]:
    """A valid synthetic message; changes replace top-level keys, DROP removes one."""
    event_id = PREFIX + case
    event_time, updated = now - timedelta(hours=1), now - timedelta(minutes=50)
    geometry = {"type": "Point", "coordinates": [-3.7, 40.4, 10.0]}
    message: dict[str, Any] = {
        "id": event_id,
        "time": _ms(event_time),
        "updated": _ms(updated),
        "mag": 4.2,
        "place": "Synthetic test",
        "geometry": geometry,
        "properties": {"magType": "ml", "type": "earthquake"},
        "ingested_at": updated.isoformat(),
        "synthetic": True,
        "synthetic_case": case,
    }
    message["original_event"] = {"type": "Feature", "id": event_id, "geometry": geometry, "properties": {"mag": 4.2}}
    message.update(changes)
    return {key: value for key, value in message.items() if value is not DROP}


def _point(*values: Any) -> dict[str, Any]:
    return {"type": "Point", "coordinates": list(values)}


def build_cases(now: datetime | None = None) -> tuple[SyntheticCase, ...]:
    now = now or datetime.now(timezone.utc)
    marker = "synthetic"
    cases: list[SyntheticCase] = []

    def add(case: str, description: str, outcome: str, codes: tuple[str, ...], message: Any = None, **kw: Any) -> None:
        cases.append(SyntheticCase(case, description, base(case, now) if message is None else message, outcome, codes, **kw))

    def quarantine(case: str, description: str, **changes: Any) -> None:
        add(case, description, QUARANTINE, (case,), base(case, now, **changes))

    # Quarantine rules.
    truncated = b'{"id": "synthetic-malformed_json", "synthetic": true, "synthetic_case": "malformed_json", "mag": '
    add("malformed_json", "Truncated JSON text", QUARANTINE, ("malformed_json",), truncated)
    add("not_an_object", "A JSON array instead of an object", QUARANTINE, ("not_an_object",),
        ["synthetic-not_an_object", "synthetic", "synthetic_case"])
    quarantine("missing_id", "No id", id=DROP)
    quarantine("invalid_id", "id is a number", id=5)
    quarantine("missing_time", "No time", time=DROP)
    quarantine("invalid_time", "time is text", time="yesterday")
    quarantine("missing_updated", "No updated", updated=DROP)
    quarantine("invalid_updated", "updated is text", updated="yesterday")
    quarantine("geometry_missing", "No geometry", geometry=DROP)
    quarantine("geometry_not_point", "A line instead of a point", geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]})
    quarantine("coordinates_missing", "Point without coordinates", geometry={"type": "Point"})
    quarantine("coordinates_not_numeric", "Longitude is text", geometry=_point("a", 40.4))
    overflow = json.dumps(base("coordinates_not_finite", now, geometry=_point(0, 40.4))).replace(
        '"coordinates": [0, 40.4]', '"coordinates": [1e999, 40.4]'
    )
    add("coordinates_not_finite", "Longitude overflows to infinity", QUARANTINE, ("coordinates_not_finite",), overflow.encode())
    quarantine("coordinates_out_of_range", "Latitude 145", geometry=_point(-3.7, 145.0, 1.0))
    add("model_constraint_violation", "Valid for the rules, but before 1900: the model refuses it", QUARANTINE,
        ("model_constraint_violation",),
        base("model_constraint_violation", now, time=-2_800_000_000_000, updated=-2_799_999_000_000),
        rules_outcome=EVENT)

    # Acceptance cases.
    add("invalid_coordinates", "Longitude and latitude both impossible", QUARANTINE, ("coordinates_out_of_range",),
        base("invalid_coordinates", now, geometry=_point(200.0, -95.0, 5.0)))
    add("null_magnitude", "Null magnitude: stored null, not rejected", EVENT, (marker,),
        base("null_magnitude", now, mag=None), country="ESP")
    add("maritime_event", "Mid-Atlantic point: no country", EVENT, (marker,),
        base("maritime_event", now, geometry=_point(-30.0, 30.0, 10.0), place="Mid-Atlantic Ridge"), country=None)

    # Exclusions.
    add("not_earthquake", "properties.type is quarry blast", EXCLUSION, ("not_earthquake",),
        base("not_earthquake", now, properties={"type": "quarry blast", "magType": "ml"}))
    add("missing_type", "properties.type missing", EXCLUSION, ("missing_type",),
        base("missing_type", now, properties={"magType": "ml"}))

    # Flags.
    def flagged(case: str, description: str, *flags: str, **changes: Any) -> None:
        add(case, description, EVENT, tuple(sorted({marker, *flags})), base(case, now, **changes), country="ESP")

    flagged("negative_depth", "Depth below zero", "negative_depth", geometry=_point(-3.7, 40.4, -2.7))
    flagged("magnitude_out_of_range", "Magnitude 10.5", "magnitude_out_of_range", mag=10.5)
    flagged("depth_out_of_range", "Depth 900 km", "depth_out_of_range", geometry=_point(-3.7, 40.4, 900))
    flagged("future_time", "Occurrence 10 minutes ahead", "future_time",
            time=_ms(now + timedelta(minutes=10)), updated=_ms(now + timedelta(minutes=10)))
    flagged("updated_before_time", "updated earlier than time", "updated_before_time", updated=_ms(now - timedelta(hours=2)))
    flagged("magnitude_from_text", "Magnitude as numeric text", "magnitude_from_text", mag="4.2")
    flagged("depth_from_text", "Depth as numeric text", "depth_from_text", geometry=_point(-3.7, 40.4, "10"))
    flagged("magnitude_not_numeric", "Magnitude as non-numeric text", "magnitude_not_numeric", mag="abc")
    flagged("depth_not_numeric", "Depth as non-numeric text", "depth_not_numeric", geometry=_point(-3.7, 40.4, "deep"))
    flagged("extra_coordinates", "Four coordinate values", "extra_coordinates", geometry=_point(-3.7, 40.4, 10.0, 5.0))
    flagged("synthetic", "Plain synthetic marker")
    return tuple(cases)


def restart_batch(count: int, now: datetime | None = None) -> list[dict[str, Any]]:
    """count valid synthetic events with distinct ids, for the restart test."""
    now = now or datetime.now(timezone.utc)
    messages = []
    for index in range(count):
        lon, lat = -179.0 + (index * 7.3) % 358.0, -80.0 + (index * 3.7) % 160.0
        geometry = _point(round(lon, 3), round(lat, 3), float(index % 300))
        message = base(
            f"batch-{index:05d}", now, mag=round(1.0 + (index % 60) / 10, 1), geometry=geometry,
            time=_ms(now - timedelta(hours=1, seconds=index)),
            updated=_ms(now - timedelta(minutes=50, seconds=index)),
        )
        message["synthetic_case"] = "batch"
        message["original_event"] = {"type": "Feature", "id": message["id"], "geometry": geometry, "properties": {"mag": message["mag"]}}
        messages.append(message)
    return messages


CASES = build_cases()
