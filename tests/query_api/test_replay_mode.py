"""GET /api/eventos with mode=replay: identified, historical and separate from real data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.db.helpers import Version

T2025 = datetime(2025, 6, 10, 12, 0, tzinfo=timezone.utc)
LABEL = "REPRODUCCIÓN"


def version(event_id: str, event_time: datetime = T2025, **changes) -> Version:
    changes.setdefault("updated_at", event_time + timedelta(minutes=5))
    return Version(event_id, event_time=event_time, **changes)


def ids(response) -> list[str]:
    return [f["id"] for f in response.json()["features"]]


def test_replay_returns_only_replay_events_with_replayed_at(api) -> None:
    replayed = datetime.now(timezone.utc) - timedelta(minutes=30)
    api.add_event(version("RP"), schema="replay", replayed_at=replayed)
    api.add_event(version("LIVE", datetime.now(timezone.utc) - timedelta(hours=1)))

    response = api.get("/api/eventos", mode="replay")

    assert response.status == 200
    assert ids(response) == ["RP"]
    props = response.json()["features"][0]["properties"]
    assert props["replayed_at"] == int(replayed.timestamp() * 1000)
    assert props["synthetic"] is False
    assert ids(api.get("/api/eventos")) == ["LIVE"]


def test_replay_has_no_24_hour_window(api) -> None:
    api.add_event(version("OLD"), schema="replay")

    body = api.get("/api/eventos", mode="replay").json()

    assert [f["id"] for f in body["features"]] == ["OLD"]
    assert body["metadata"]["period"]["default_applied"] is False
    assert body["metadata"]["period"]["start"] is None


def test_time_magnitude_country_filters_and_pagination_apply_in_replay(api) -> None:
    api.add_event(version("A", T2025, magnitude=5.0, country_id="ESP"), schema="replay")
    api.add_event(version("B", T2025 + timedelta(hours=1), magnitude=3.0, country_id="ESP"), schema="replay")
    api.add_event(version("C", T2025 + timedelta(hours=2), magnitude=6.0, country_id="JPN"), schema="replay")
    api.add_event(version("D", T2025 + timedelta(days=5), magnitude=6.0, country_id="ESP"), schema="replay")

    start = (T2025 + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (T2025 + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    assert ids(api.get("/api/eventos", mode="replay", start=start, end=end)) == ["C", "B"]
    assert ids(api.get("/api/eventos", mode="replay", min_mag="5")) == ["D", "C", "A"]
    assert ids(api.get("/api/eventos", mode="replay", country_id="JPN")) == ["C"]

    page = api.get("/api/eventos", mode="replay", limit=2).json()
    assert [f["id"] for f in page["features"]] == ["D", "C"]
    assert page["metadata"]["total"] == 4 and page["metadata"]["truncated"] is True
    assert page["metadata"]["next_offset"] == 2
    rest = api.get("/api/eventos", mode="replay", limit=2, offset=2).json()
    assert [f["id"] for f in rest["features"]] == ["B", "A"]


def test_label_and_mode_in_every_replay_response_even_when_empty(api) -> None:
    empty = api.get("/api/eventos", mode="replay").json()
    assert empty["features"] == []
    assert empty["metadata"]["mode"] == "replay"
    assert empty["metadata"]["label"] == LABEL
    assert empty["metadata"]["last_replayed_at"] is None

    api.add_event(version("X"), schema="replay")
    full = api.get("/api/eventos", mode="replay").json()
    assert full["metadata"]["mode"] == "replay" and full["metadata"]["label"] == LABEL

    live = api.get("/api/eventos").json()["metadata"]
    assert live["mode"] == "live" and "label" not in live


def test_last_ingestion_is_from_core_and_last_replayed_at_is_the_maximum(api) -> None:
    requested = (datetime.now(timezone.utc) - timedelta(minutes=7)).replace(microsecond=0)
    api.add_extraction(requested_at=requested)
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    recent = datetime.now(timezone.utc) - timedelta(minutes=10)
    api.add_event(version("R1"), schema="replay", replayed_at=old)
    api.add_event(version("R2", T2025 + timedelta(hours=1)), schema="replay", replayed_at=recent)

    meta = api.get("/api/eventos", mode="replay").json()["metadata"]

    assert meta["last_ingestion"] == int(requested.timestamp() * 1000)
    assert meta["last_replayed_at"] == int(recent.timestamp() * 1000)


def test_same_event_id_in_both_schemas_keeps_each_own_values(api) -> None:
    now_event = datetime.now(timezone.utc) - timedelta(hours=1)
    api.add_event(version("SAME", now_event, magnitude=2.0, place="Live place"))
    api.add_event(version("SAME", T2025, magnitude=7.0, place="Replay place"), schema="replay")

    live = api.get("/api/eventos").json()["features"]
    replay = api.get("/api/eventos", mode="replay").json()["features"]

    assert [(f["id"], f["properties"]["mag"], f["properties"]["place"]) for f in live] == [("SAME", 2.0, "Live place")]
    assert [(f["id"], f["properties"]["mag"], f["properties"]["place"]) for f in replay] == [
        ("SAME", 7.0, "Replay place")
    ]


def test_synthetic_events_are_marked_and_can_be_excluded(api) -> None:
    api.add_event(version("synthetic-case", T2025 + timedelta(hours=1)), schema="replay")
    api.add_event(version("flagged", T2025 + timedelta(hours=2), quality_flags=["synthetic"]), schema="replay")
    api.add_event(version("REAL", T2025), schema="replay")

    shown = api.get("/api/eventos", mode="replay").json()["features"]
    flags = {f["id"]: f["properties"]["synthetic"] for f in shown}
    assert flags == {"synthetic-case": True, "flagged": True, "REAL": False}

    filtered = api.get("/api/eventos", mode="replay", exclude_synthetic="true")
    assert ids(filtered) == ["REAL"]
    assert filtered.json()["metadata"]["total"] == 1


def test_invalid_mode_is_422_and_missing_mode_is_live(api) -> None:
    api.add_event(version("LIVE", datetime.now(timezone.utc) - timedelta(hours=1)))
    api.add_event(version("RP"), schema="replay")

    bad = api.get("/api/eventos", mode="otro")
    assert bad.status == 422
    assert bad.json()["error"] == "invalid_parameters"
    assert bad.json()["detail"][0]["param"] == "mode"

    default = api.get("/api/eventos")
    assert default.json()["metadata"]["mode"] == "live"
    assert ids(default) == ["LIVE"]
