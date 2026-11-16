"""The map follows what the consumer writes: new, repeated, revised, late and damaged messages."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from consumer.app import rules
from tests.db.helpers import Message, Version
from tests.synthetic.cases import CASES

UPDATED = datetime.now(timezone.utc) - timedelta(hours=2)


def event(event_id: str = "FLOW", minutes: int = 0, **changes) -> Version:
    changes.setdefault("event_time", datetime.now(timezone.utc) - timedelta(hours=3))
    return Version(event_id, updated_at=UPDATED + timedelta(minutes=minutes), **changes)


def first_feature(api, event_id: str = "FLOW") -> dict:
    return next(f for f in api.get("/api/eventos").json()["features"] if f["id"] == event_id)


def test_new_event_is_visible_after_it_is_written(api) -> None:
    assert api.get("/api/eventos").json()["features"] == []

    assert api.add_event(event(magnitude=4.2)) == "new"

    body = api.get("/api/eventos").json()
    assert body["metadata"]["total"] == 1
    assert body["features"][0]["properties"]["mag"] == 4.2


def test_the_same_message_twice_does_not_change_the_total(api) -> None:
    message = Message("earthquakes.live", 0, 1)
    version = event()

    assert api.add_event(version, message=message) == "new"
    before = api.get("/api/eventos").json()
    assert api.add_event(version, message=message) == "duplicate"
    after = api.get("/api/eventos").json()

    assert after["metadata"]["total"] == before["metadata"]["total"] == 1
    assert after["features"] == before["features"]


def test_a_revision_changes_magnitude_updated_and_country(api) -> None:
    api.add_event(event(magnitude=4.0, country_id="ESP"))
    before = first_feature(api)["properties"]

    assert api.add_event(event(minutes=10, magnitude=4.9, country_id="FRA")) == "revised"

    body = api.get("/api/eventos").json()
    assert body["metadata"]["total"] == 1
    after = body["features"][0]["properties"]
    assert after["mag"] == 4.9
    assert after["updated"] > before["updated"]
    assert before["country_id"] == "ESP"
    assert after["country_id"] == "FRA"


def test_a_late_older_version_changes_nothing(api) -> None:
    api.add_event(event(minutes=10, magnitude=4.9))
    before = api.get("/api/eventos").json()["features"]

    assert api.add_event(event(minutes=0, magnitude=3.0)) == "stale"

    assert api.get("/api/eventos").json()["features"] == before


def test_a_message_with_invalid_coordinates_is_quarantined_not_shown(api) -> None:
    case = next(c for c in CASES if c.case == "invalid_coordinates")
    # The same damaged message as a real one (no synthetic marker): quarantine counts only those.
    message = json.loads(case.raw())
    for key in ("synthetic", "synthetic_case"):
        message.pop(key, None)
    message["id"] = "damaged-1"
    verdict = rules.evaluate(json.dumps(message).encode(), datetime.now(timezone.utc))
    assert isinstance(verdict, rules.Quarantine)
    assert "coordinates_out_of_range" in verdict.reasons
    assert verdict.synthetic is False

    before = api.get("/api/eventos").json()["metadata"]["quarantined"]
    api.add_quarantine(
        verdict.reasons, event_id=verdict.event_id, payload=verdict.payload, is_synthetic=verdict.synthetic
    )
    body = api.get("/api/eventos").json()

    assert body["features"] == []
    assert body["metadata"]["total"] == 0
    after = body["metadata"]["quarantined"]
    assert after["invalid_geometry"] == before["invalid_geometry"] + 1
    assert after["total"] == before["total"] + 1


def test_synthetic_quarantine_is_not_counted(api) -> None:
    case = next(c for c in CASES if c.case == "invalid_coordinates")
    verdict = rules.evaluate(case.raw(), datetime.now(timezone.utc))
    assert isinstance(verdict, rules.Quarantine) and verdict.synthetic is True

    api.add_quarantine(
        verdict.reasons, event_id=verdict.event_id, payload=verdict.payload, is_synthetic=True
    )

    assert api.get("/api/eventos").json()["metadata"]["quarantined"] == {"total": 0, "invalid_geometry": 0}


def test_non_geometry_quarantine_counts_in_total_only(api) -> None:
    api.add_quarantine(["missing_id"])

    assert api.get("/api/eventos").json()["metadata"]["quarantined"] == {"total": 1, "invalid_geometry": 0}
