"""One table of cases per rule of specs/004-consumer-quality/contracts/rules-catalog.md."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from consumer.app.rules import Accepted, Exclusion, Quarantine, evaluate

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
DROP = object()


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def message(**changes: Any) -> dict[str, Any]:
    """A valid flat message (as the producer publishes it); changes replace top-level keys.

    The sentinel DROP removes the key.
    """
    event_time = NOW - timedelta(hours=1)
    updated = NOW - timedelta(minutes=50)
    geometry = {"type": "Point", "coordinates": [-3.7, 40.4, 10.0]}
    base: dict[str, Any] = {
        "id": "E1",
        "time": ms(event_time),
        "updated": ms(updated),
        "mag": 4.2,
        "place": "Test",
        "geometry": geometry,
        "properties": {"magType": "ml", "type": "earthquake"},
        "ingested_at": updated.isoformat(),
    }
    base["original_event"] = {"type": "Feature", "id": "E1", "geometry": geometry, "properties": {"mag": 4.2}}
    base.update(changes)
    return {key: value for key, value in base.items() if value is not DROP}


def run(payload: Any) -> Any:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return evaluate(raw, NOW)


def coords(*values: Any) -> dict[str, Any]:
    return {"type": "Point", "coordinates": list(values)}


def accepted(payload: dict[str, Any]) -> Accepted:
    result = run(payload)
    assert isinstance(result, Accepted), result
    return result


# ----- accepted: stored values and flags -------------------------------------------------------


def test_valid_message_is_accepted_without_flags() -> None:
    result = accepted(message())
    assert result.flags == [] and result.synthetic is False
    event = result.event
    assert (event.external_id, event.magnitude, event.mag_type, event.place) == ("E1", 4.2, "ml", "Test")
    assert (event.longitude, event.latitude, event.depth_km) == (-3.7, 40.4, 10.0)
    assert event.event_time == NOW - timedelta(hours=1) and event.updated == NOW - timedelta(minutes=50)
    assert event.event_time.tzinfo is not None
    assert result.original["type"] == "Feature"
    assert result.produced_at == NOW - timedelta(minutes=50)


def test_original_is_the_decoded_message_without_original_event() -> None:
    payload = message(original_event=DROP)
    assert accepted(payload).original == payload


def test_null_magnitude_type_depth_and_place_stay_null_without_flags() -> None:
    result = accepted(message(mag=None, place=None, geometry=coords(-3.7, 40.4, None), properties={"type": "earthquake"}))
    event = result.event
    assert (event.magnitude, event.mag_type, event.depth_km, event.place) == (None, None, None, None)
    assert result.flags == []


def test_two_coordinates_have_null_depth() -> None:
    result = accepted(message(geometry=coords(-3.7, 40.4)))
    assert result.event.depth_km is None and result.flags == []


def test_negative_magnitude_is_kept_without_flag() -> None:
    result = accepted(message(mag=-0.5))
    assert result.event.magnitude == -0.5 and result.flags == []


def test_zero_magnitude_is_kept() -> None:
    assert accepted(message(mag=0)).event.magnitude == 0


def test_negative_depth_is_flagged() -> None:
    result = accepted(message(geometry=coords(-3.7, 40.4, -2.7)))
    assert result.event.depth_km == -2.7 and result.flags == ["negative_depth"]


@pytest.mark.parametrize("mag", [10.5, -3])
def test_magnitude_out_of_range_is_flagged_and_kept(mag: float) -> None:
    result = accepted(message(mag=mag))
    assert result.event.magnitude == mag and result.flags == ["magnitude_out_of_range"]


@pytest.mark.parametrize("mag", [10, -2])
def test_magnitude_range_limits_are_valid(mag: float) -> None:
    assert accepted(message(mag=mag)).flags == []


def test_depth_over_800_is_flagged() -> None:
    result = accepted(message(geometry=coords(-3.7, 40.4, 900)))
    assert result.event.depth_km == 900 and result.flags == ["depth_out_of_range"]


def test_old_event_is_accepted_without_flag() -> None:
    old = NOW - timedelta(days=30)
    assert accepted(message(time=ms(old), updated=ms(old))).flags == []


def test_future_time_beyond_five_minutes_is_flagged() -> None:
    future = NOW + timedelta(minutes=10)
    assert accepted(message(time=ms(future), updated=ms(future))).flags == ["future_time"]


def test_future_time_within_five_minutes_is_not_flagged() -> None:
    near = NOW + timedelta(minutes=2)
    assert accepted(message(time=ms(near), updated=ms(near))).flags == []


def test_updated_before_time_is_flagged() -> None:
    result = accepted(message(time=ms(NOW - timedelta(hours=1)), updated=ms(NOW - timedelta(hours=2))))
    assert result.flags == ["updated_before_time"]


def test_numeric_text_magnitude_is_converted_and_flagged() -> None:
    result = accepted(message(mag="4.2"))
    assert result.event.magnitude == 4.2 and result.flags == ["magnitude_from_text"]


def test_non_numeric_text_magnitude_is_null_and_flagged() -> None:
    result = accepted(message(mag="abc"))
    assert result.event.magnitude is None and result.flags == ["magnitude_not_numeric"]


def test_numeric_text_depth_is_converted_and_flagged() -> None:
    result = accepted(message(geometry=coords(-3.7, 40.4, "12.5")))
    assert result.event.depth_km == 12.5 and result.flags == ["depth_from_text"]


def test_non_numeric_text_depth_is_null_and_flagged() -> None:
    result = accepted(message(geometry=coords(-3.7, 40.4, "deep")))
    assert result.event.depth_km is None and result.flags == ["depth_not_numeric"]


def test_extra_coordinates_are_flagged() -> None:
    result = accepted(message(geometry=coords(-3.7, 40.4, 10.0, 99.0)))
    assert result.event.depth_km == 10.0 and result.flags == ["extra_coordinates"]


def test_flags_are_sorted_and_unique() -> None:
    result = accepted(
        message(mag=-3, geometry=coords(-3.7, 40.4, -5, 1), time=ms(NOW - timedelta(hours=1)), updated=ms(NOW - timedelta(hours=3)))
    )
    assert result.flags == sorted(set(result.flags))
    assert set(result.flags) == {"extra_coordinates", "magnitude_out_of_range", "negative_depth", "updated_before_time"}


def test_boundary_coordinates_are_valid() -> None:
    assert accepted(message(geometry=coords(180, -90, 1))).event.longitude == 180
    assert accepted(message(geometry=coords(-180, 90, 1))).event.latitude == 90


def test_synthetic_message_is_marked() -> None:
    result = accepted(message(synthetic=True))
    assert result.synthetic is True and "synthetic" in result.flags


# ----- quarantine ------------------------------------------------------------------------------

QUARANTINE_CASES = [
    ("missing_id", message(id=DROP)),
    ("invalid_id", message(id=123)),
    ("invalid_id", message(id="  ")),
    ("missing_time", message(time=DROP)),
    ("invalid_time", message(time="yesterday")),
    ("missing_updated", message(updated=DROP)),
    ("invalid_updated", message(updated="2026-01-01")),
    ("geometry_missing", message(geometry=DROP)),
    ("geometry_not_point", message(geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]})),
    ("coordinates_missing", message(geometry={"type": "Point"})),
    ("coordinates_missing", message(geometry=coords(1))),
    ("coordinates_not_numeric", message(geometry=coords("a", 40))),
    ("coordinates_out_of_range", message(geometry=coords(-3.7, 145, 1))),
    ("coordinates_out_of_range", message(geometry=coords(-200, 40, 1))),
]


@pytest.mark.parametrize(("code", "payload"), QUARANTINE_CASES)
def test_intractable_message_is_quarantined(code: str, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload).encode()
    result = evaluate(raw, NOW)
    assert isinstance(result, Quarantine), result
    assert result.reasons == [code]
    assert result.payload == json.loads(raw) and result.raw_text is None
    assert code in result.detail


def test_overflowing_coordinate_is_not_finite() -> None:
    # json.dumps would write Infinity, so the literal is built by hand: 1e999 parses to inf.
    raw = json.dumps(message(geometry=coords(0, 40))).replace('"coordinates": [0, 40]', '"coordinates": [1e999, 40]').encode()
    result = evaluate(raw, NOW)
    assert isinstance(result, Quarantine) and result.reasons == ["coordinates_not_finite"]


def test_quarantine_keeps_the_event_id_when_there_is_one() -> None:
    result = run(message(time=DROP))
    assert isinstance(result, Quarantine) and result.event_id == "E1"


@pytest.mark.parametrize("raw", [b"{not json", b'{"id": "E1", "mag": NaN}', b"\xff\xfe", b'{"mag": Infinity}'])
def test_malformed_json_keeps_the_text(raw: bytes) -> None:
    result = evaluate(raw, NOW)
    assert isinstance(result, Quarantine)
    assert result.reasons == ["malformed_json"] and result.payload is None and result.raw_text is not None


@pytest.mark.parametrize("raw", [b"[1, 2]", b'"text"', b"42", b"null"])
def test_json_that_is_not_an_object_is_quarantined(raw: bytes) -> None:
    result = evaluate(raw, NOW)
    assert isinstance(result, Quarantine) and result.reasons == ["not_an_object"]
    assert result.payload == json.loads(raw) and result.event_id is None


def test_every_reason_is_listed_not_only_the_first() -> None:
    result = run(message(id=DROP, time="x", updated=DROP, geometry=coords(-3.7, 145)))
    assert isinstance(result, Quarantine)
    assert result.reasons == ["missing_id", "invalid_time", "missing_updated", "coordinates_out_of_range"]
    assert all(code in result.detail for code in result.reasons)


def test_quarantine_beats_flags_and_exclusion() -> None:
    result = run(message(mag=-5, properties={"type": "quarry blast"}, geometry=coords(500, 40)))
    assert isinstance(result, Quarantine) and result.reasons == ["coordinates_out_of_range"]


def test_synthetic_quarantine_is_marked() -> None:
    result = run(message(id=DROP, synthetic=True))
    assert isinstance(result, Quarantine) and result.synthetic is True
    assert run(message(id=DROP)).synthetic is False


# ----- exclusion -------------------------------------------------------------------------------


def test_other_event_type_is_excluded() -> None:
    payload = message(properties={"type": "quarry blast", "mag": 2.0})
    result = run(payload)
    assert isinstance(result, Exclusion)
    assert (result.reason_code, result.event_id, result.event_type) == ("not_earthquake", "E1", "quarry blast")
    assert result.updated_at == NOW - timedelta(minutes=50) and result.synthetic is False
    assert result.feature == payload["original_event"]


def test_missing_type_is_excluded() -> None:
    result = run(message(properties={"magType": "ml"}))
    assert isinstance(result, Exclusion)
    assert (result.reason_code, result.event_type) == ("missing_type", None)


def test_synthetic_exclusion_is_marked() -> None:
    assert run(message(properties={"type": "explosion"}, synthetic=True)).synthetic is True


def test_evaluation_does_not_mutate_input() -> None:
    payload = message()
    before = copy.deepcopy(payload)
    run(payload)
    assert payload == before
