import json
from datetime import datetime, timedelta, timezone

import pytest

from producer.app.replay.message import build_replay_message, encode

WHEN = datetime(2026, 11, 16, 10, 30, 0, tzinfo=timezone.utc)


def feature(event_id, time, updated, mag):
    return {
        "type": "Feature",
        "id": event_id,
        "geometry": {"type": "Point", "coordinates": [-122.1, 37.2, 8.0]},
        "properties": {"time": time, "updated": updated, "mag": mag, "place": "5 km N of Somewhere"},
    }


FEATURES = [
    feature("us7000aaaa", 1_600_000_000_123, 1_600_000_999_999, 4.5),
    feature("ci40000001", 946_684_800_000, 1_700_000_000_000, 2.1),
    feature("nc70000002", 1_500_000_000_000, 1_500_000_000_000, None),
]


@pytest.mark.parametrize("feat", FEATURES)
def test_time_and_updated_are_untouched(feat):
    message = build_replay_message(feat, extraction_id=7, replayed_at=WHEN, run="r1")
    decoded = json.loads(encode(message))
    assert decoded["time"] == feat["properties"]["time"]
    assert decoded["updated"] == feat["properties"]["updated"]
    assert decoded["original_event"] == feat
    assert decoded["id"] == feat["id"]
    assert decoded["mag"] == feat["properties"]["mag"]


def test_null_magnitude_is_kept_null():
    message = build_replay_message(FEATURES[2], extraction_id=None, replayed_at=WHEN, run="r1")
    assert message["mag"] is None
    assert message["extraction_id"] is None


def test_mode_source_and_run():
    message = build_replay_message(FEATURES[0], extraction_id=3, replayed_at=WHEN, run="run-x")
    assert message["mode"] == "replay"
    assert message["source"] == "usgs_catalog"
    assert message["replay_run"] == "run-x"
    assert message["extraction_id"] == 3
    assert "synthetic" not in message


def test_replayed_at_is_utc_with_z():
    local = datetime(2026, 11, 16, 12, 30, 0, tzinfo=timezone(timedelta(hours=2)))
    message = build_replay_message(FEATURES[0], extraction_id=1, replayed_at=local, run="r")
    assert message["replayed_at"] == "2026-11-16T10:30:00Z"
    assert message["ingested_at"] == message["replayed_at"]


def test_synthetic_marks():
    message = build_replay_message(FEATURES[0], extraction_id=None, replayed_at=WHEN, run="r", synthetic_case="dup")
    assert message["synthetic"] is True
    assert message["synthetic_case"] == "dup"


def test_encode_is_compact_utf8_and_key_matches_id():
    feat = feature("us7000bbbb", 1, 2, 3.0)
    feat["properties"]["place"] = "Perú"
    message = build_replay_message(feat, extraction_id=1, replayed_at=WHEN, run="r")
    raw = encode(message)
    assert " " not in raw.decode("utf-8").replace("Perú", "").replace("5 km", "")
    assert "Perú".encode("utf-8") in raw
    assert message["id"].encode("utf-8") == b"us7000bbbb"


def test_nan_is_rejected():
    feat = feature("us7000cccc", 1, 2, float("nan"))
    message = build_replay_message(feat, extraction_id=1, replayed_at=WHEN, run="r")
    with pytest.raises(ValueError):
        encode(message)
