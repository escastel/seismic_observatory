"""Behavior of GET /api/eventos in live mode against the real test database (spec 006, US1)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from tests.db.helpers import Version

START = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)

METADATA_KEYS = {
    "generated", "last_ingestion", "mode", "count", "total", "truncated", "limit", "offset",
    "next_offset", "period", "null_magnitude", "quarantined",
}


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def ago(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def version(event_id: str, event_time: datetime, **changes) -> Version:
    changes.setdefault("updated_at", event_time + timedelta(minutes=5))
    return Version(event_id, event_time=event_time, **changes)


def ids(response) -> list[str]:
    return [feature["id"] for feature in response.json()["features"]]


def test_metadata_structure_and_feature_shape(api) -> None:
    event_time = ago(2).replace(microsecond=0)
    api.add_event(version("E1", event_time, magnitude=3.2, longitude=-3.7, latitude=40.4, depth_km=12.0))
    api.add_extraction()

    response = api.get("/api/eventos")

    assert response.status == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["type"] == "FeatureCollection"
    meta = body["metadata"]
    assert METADATA_KEYS <= set(meta)
    assert "label" not in meta
    assert meta["mode"] == "live"
    assert (meta["count"], meta["total"], meta["truncated"]) == (1, 1, False)
    assert (meta["limit"], meta["offset"], meta["next_offset"]) == (1000, 0, None)
    assert isinstance(meta["generated"], int) and isinstance(meta["last_ingestion"], int)
    assert meta["period"]["default_applied"] is True
    assert meta["period"]["end"] is None
    assert meta["period"]["start"] < meta["generated"]
    assert meta["null_magnitude"] == {"count": 0, "excluded": False}
    assert meta["quarantined"] == {"total": 0, "invalid_geometry": 0}

    feature = body["features"][0]
    assert feature["type"] == "Feature" and feature["id"] == "E1"
    assert feature["geometry"] == {"type": "Point", "coordinates": [-3.7, 40.4, 12.0]}
    props = feature["properties"]
    assert props["mag"] == 3.2 and props["magType"] == "ml"
    assert props["place"] == "Madrid, Spain"
    assert props["country_id"] == "ESP" and props["country_name"]
    assert props["continent"] and props["subregion"]
    assert props["time"] == int(event_time.timestamp() * 1000)
    assert isinstance(props["time"], int) and isinstance(props["updated"], int)
    assert "replayed_at" not in props and "synthetic" not in props


def test_no_events_is_200_with_empty_features(api) -> None:
    response = api.get("/api/eventos")

    assert response.status == 200
    body = response.json()
    assert body["features"] == []
    assert (body["metadata"]["count"], body["metadata"]["total"]) == (0, 0)
    assert body["metadata"]["last_ingestion"] is None


def test_nullable_values_are_null_never_nan(api) -> None:
    api.add_event(
        version("N1", ago(1), magnitude=None, mag_type=None, depth_km=None, country_id=None, place=None)
    )

    response = api.get("/api/eventos")

    assert "NaN" not in response.text and "Infinity" not in response.text
    feature = response.json()["features"][0]
    assert feature["properties"]["mag"] is None
    assert feature["properties"]["country_id"] is None
    assert feature["properties"]["country_name"] is None
    assert feature["geometry"]["coordinates"][2] is None
    for value in feature["geometry"]["coordinates"]:
        assert value is None or math.isfinite(value)


def test_event_with_three_versions_appears_once_with_the_current_one(api) -> None:
    event_time = ago(3)
    base = event_time + timedelta(minutes=5)
    api.add_event(version("V1", event_time, updated_at=base, magnitude=4.0))
    api.add_event(version("V1", event_time, updated_at=base + timedelta(minutes=10), magnitude=4.5))
    api.add_event(version("V1", event_time, updated_at=base + timedelta(minutes=20), magnitude=4.8))

    body = api.get("/api/eventos").json()

    assert ids(api.get("/api/eventos")) == ["V1"]
    assert body["metadata"]["total"] == 1
    assert body["features"][0]["properties"]["mag"] == 4.8


def test_default_window_is_24_hours(api) -> None:
    api.add_event(version("IN", ago(23)))
    api.add_event(version("OUT", ago(25)))

    response = api.get("/api/eventos")

    assert ids(response) == ["IN"]
    assert response.json()["metadata"]["total"] == 1


def test_start_is_inclusive_and_end_is_exclusive(api) -> None:
    api.add_event(version("BEFORE", START - timedelta(seconds=1)))
    api.add_event(version("AT_START", START))
    api.add_event(version("INSIDE", START + timedelta(hours=12)))
    api.add_event(version("AT_END", END))

    response = api.get("/api/eventos", start=iso(START), end=iso(END))

    assert ids(response) == ["INSIDE", "AT_START"]
    meta = response.json()["metadata"]
    assert meta["period"] == {
        "start": int(START.timestamp() * 1000),
        "end": int(END.timestamp() * 1000),
        "default_applied": False,
    }


def test_start_without_end_has_no_upper_bound_and_no_default_window(api) -> None:
    api.add_event(version("OLD", START + timedelta(days=1)))

    response = api.get("/api/eventos", start=iso(START))

    assert ids(response) == ["OLD"]
    assert response.json()["metadata"]["period"]["default_applied"] is False


def test_end_without_start_covers_the_24_hours_before_end(api) -> None:
    api.add_event(version("IN", END - timedelta(hours=23)))
    api.add_event(version("OUT", END - timedelta(hours=25)))
    api.add_event(version("AT_END", END))

    response = api.get("/api/eventos", end=iso(END))

    assert ids(response) == ["IN"]
    assert response.json()["metadata"]["period"]["default_applied"] is True


def test_min_mag_includes_the_exact_value(api) -> None:
    api.add_event(version("EXACT", ago(1), magnitude=4.5))
    api.add_event(version("ABOVE", ago(2), magnitude=5.1))
    api.add_event(version("BELOW", ago(3), magnitude=4.4))

    response = api.get("/api/eventos", min_mag="4.5")

    assert ids(response) == ["EXACT", "ABOVE"]
    assert response.json()["metadata"]["total"] == 2


def test_country_filter(api) -> None:
    api.add_event(version("ES", ago(1), country_id="ESP"))
    api.add_event(version("JP", ago(2), country_id="JPN", longitude=139.7, latitude=35.7))

    assert ids(api.get("/api/eventos", country_id="JPN")) == ["JP"]
    assert ids(api.get("/api/eventos", country_id="ESP")) == ["ES"]
    assert ids(api.get("/api/eventos", country_id="FRA")) == []


def test_the_three_filters_combine(api) -> None:
    api.add_event(version("MATCH", START + timedelta(hours=5), magnitude=5.0, country_id="ESP"))
    api.add_event(version("WEAK", START + timedelta(hours=6), magnitude=3.0, country_id="ESP"))
    api.add_event(version("ABROAD", START + timedelta(hours=7), magnitude=5.0, country_id="JPN"))
    api.add_event(version("LATE", END + timedelta(hours=1), magnitude=5.0, country_id="ESP"))

    response = api.get(
        "/api/eventos", start=iso(START), end=iso(END), min_mag="4.0", country_id="ESP"
    )

    assert ids(response) == ["MATCH"]
    assert response.json()["metadata"]["total"] == 1


def test_null_magnitude_with_and_without_min_mag(api) -> None:
    api.add_event(version("NULLMAG", ago(1), magnitude=None))
    api.add_event(version("BIG", ago(2), magnitude=5.0))

    without = api.get("/api/eventos").json()
    assert sorted(ids(api.get("/api/eventos"))) == ["BIG", "NULLMAG"]
    nullmag = next(f for f in without["features"] if f["id"] == "NULLMAG")
    assert nullmag["properties"]["mag"] is None
    assert without["metadata"]["null_magnitude"] == {"count": 1, "excluded": False}

    filtered = api.get("/api/eventos", min_mag="1.0").json()
    assert [f["id"] for f in filtered["features"]] == ["BIG"]
    assert filtered["metadata"]["null_magnitude"] == {"count": 1, "excluded": True}
    assert filtered["metadata"]["total"] == 1


def test_synthetic_event_in_core_is_not_shown_in_live_mode(api) -> None:
    api.add_event(version("synthetic-case", ago(1)))
    api.add_event(version("flagged", ago(2), quality_flags=["synthetic"]))
    api.add_event(version("REAL", ago(3)))

    response = api.get("/api/eventos")

    assert ids(response) == ["REAL"]
    assert response.json()["metadata"]["total"] == 1


def test_maritime_event_appears_without_country_filter_and_not_with_it(api) -> None:
    api.add_event(
        version("SEA", ago(1), country_id=None, longitude=-30.0, latitude=30.0, place="Mid-Atlantic Ridge")
    )
    api.add_event(version("LAND", ago(2), country_id="ESP"))

    everything = api.get("/api/eventos")
    sea = next(f for f in everything.json()["features"] if f["id"] == "SEA")
    assert sea["properties"]["country_id"] is None
    assert sorted(ids(everything)) == ["LAND", "SEA"]

    assert ids(api.get("/api/eventos", country_id="ESP")) == ["LAND"]


def test_order_is_time_descending_then_id_ascending(api) -> None:
    same = ago(5)
    api.add_event(version("B", same))
    api.add_event(version("A", same))
    api.add_event(version("NEWEST", ago(1)))

    assert ids(api.get("/api/eventos")) == ["NEWEST", "A", "B"]


def test_pagination_metadata(api) -> None:
    for number in range(5):
        api.add_event(version(f"P{number}", ago(1 + number)))

    first = api.get("/api/eventos", limit=2).json()
    assert [f["id"] for f in first["features"]] == ["P0", "P1"]
    assert first["metadata"]["total"] == 5
    assert first["metadata"]["truncated"] is True
    assert first["metadata"]["next_offset"] == 2

    last = api.get("/api/eventos", limit=2, offset=4).json()
    assert [f["id"] for f in last["features"]] == ["P4"]
    assert last["metadata"]["truncated"] is False
    assert last["metadata"]["next_offset"] is None
