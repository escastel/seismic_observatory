from datetime import datetime, timedelta, timezone

from consumer.app.quality import validate_event


def valid_payload() -> dict:
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "id": "event-1",
        "updated": timestamp,
        "time": timestamp,
        "mag": 4.2,
        "geometry": {"coordinates": [-70.0, -33.0, 10.0]},
    }


def test_quality_completeness_rejects_null_magnitude() -> None:
    payload = valid_payload()
    payload["mag"] = None

    event, failures = validate_event(payload)

    assert event is None
    assert {failure.dimension for failure in failures} == {"Completitud"}


def test_quality_validity_rejects_coordinates_and_magnitude_out_of_range() -> None:
    payload = valid_payload()
    payload["mag"] = 10.1
    payload["geometry"]["coordinates"] = [-181.0, -33.0]

    event, failures = validate_event(payload)

    assert event is None
    assert {failure.dimension for failure in failures} == {"Validez"}
    assert {failure.reason_code for failure in failures} == {
        "magnitude_out_of_range",
        "coordinates_out_of_range",
    }


def test_quality_exactness_rejects_non_numeric_depth() -> None:
    payload = valid_payload()
    payload["geometry"]["coordinates"][2] = "unknown"

    event, failures = validate_event(payload)

    assert event is None
    assert failures[0].dimension == "Exactitud"


def test_quality_consistency_rejects_invalid_event_time() -> None:
    payload = valid_payload()
    payload["time"] = "not-a-timestamp"

    event, failures = validate_event(payload)

    assert event is None
    assert failures[0].dimension == "Consistencia"


def test_quality_timeliness_rejects_invalid_updated_timestamp() -> None:
    payload = valid_payload()
    payload["updated"] = "not-a-timestamp"

    event, failures = validate_event(payload)

    assert event is None
    assert failures[0].dimension == "Oportunidad"


def test_quality_uniqueness_rejects_an_observed_id() -> None:
    event, failures = validate_event(valid_payload(), seen_ids={"event-1"})

    assert event is None
    assert failures[0].dimension == "Unicidad"


def test_quality_accepts_boundary_magnitudes() -> None:
    for magnitude in (0.0, 10.0):
        payload = valid_payload()
        payload["mag"] = magnitude

        event, failures = validate_event(payload)

        assert event is not None
        assert failures == []


def test_quality_rejects_non_finite_magnitude() -> None:
    payload = valid_payload()
    payload["mag"] = float("nan")

    event, failures = validate_event(payload)

    assert event is None
    assert failures[0].dimension == "Exactitud"


def test_quality_rejects_future_event_time_beyond_tolerance() -> None:
    now = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
    payload = valid_payload()
    future = now + timedelta(seconds=301)
    payload["time"] = int(future.timestamp() * 1000)

    event, failures = validate_event(payload, now=now)

    assert event is None
    assert [(failure.dimension, failure.reason_code) for failure in failures] == [
        ("Frescura", "future_timestamp")
    ]


def test_quality_rejects_stale_raw_event() -> None:
    now = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
    payload = valid_payload()
    stale = now - timedelta(days=7, seconds=1)
    payload["time"] = int(stale.timestamp() * 1000)

    event, failures = validate_event(payload, now=now, source_topic="earthquakes.live")

    assert event is None
    assert failures[0].reason_code == "event_too_old"
    assert failures[0].dimension == "Frescura"


def test_quality_allows_historical_replay_event() -> None:
    now = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
    payload = valid_payload()
    historical = datetime(2025, 1, 1, tzinfo=timezone.utc)
    payload["time"] = int(historical.timestamp() * 1000)

    event, failures = validate_event(payload, now=now, source_topic="earthquakes.replay")

    assert event is not None
    assert failures == []
