import json
from datetime import datetime, timezone

import pytest

from producer.app.replay.selection import select_events

D = lambda day: datetime(2025, 1, day, tzinfo=timezone.utc)  # noqa: E731
MS = lambda day, hour=0: int(datetime(2025, 1, day, hour, tzinfo=timezone.utc).timestamp() * 1000)  # noqa: E731


def feat(event_id, time, mag, updated=1, lon=0.0, lat=0.0):
    return {
        "type": "Feature",
        "id": event_id,
        "geometry": {"type": "Point", "coordinates": [lon, lat, 5.0]},
        "properties": {"time": time, "updated": updated, "mag": mag, "place": "x"},
    }


def write(tmp_path, name, features):
    path = tmp_path / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8", newline="\n")
    return path


def test_period_end_excluded_start_included(tmp_path):
    f = write(tmp_path, "a.geojson", [feat("a", MS(1), 5), feat("b", MS(2), 5), feat("c", MS(3), 5)])
    sel = select_events([f], D(1), D(3), 4.0)
    assert [x["id"] for x in sel.features] == ["a", "b"]


def test_min_magnitude_and_null_counted(tmp_path):
    f = write(tmp_path, "a.geojson", [feat("a", MS(1), 3.9), feat("b", MS(1, 1), 4.0), feat("c", MS(1, 2), None)])
    sel = select_events([f], D(1), D(2), 4.0)
    assert [x["id"] for x in sel.features] == ["b"]
    assert sel.without_magnitude_dropped == 1


def test_bbox(tmp_path):
    f = write(tmp_path, "a.geojson", [feat("in", MS(1), 5, lon=10, lat=10), feat("out", MS(1, 1), 5, lon=50, lat=10)])
    sel = select_events([f], D(1), D(2), 4.0, bbox=(0, 0, 20, 20))
    assert [x["id"] for x in sel.features] == ["in"]
    assert sel.bbox == (0.0, 0.0, 20.0, 20.0)


@pytest.mark.parametrize("bbox", [(20, 0, 10, 20), (0, 20, 10, 10), (170, 0, -170, 10), (0, 0, 1)])
def test_invalid_bbox(tmp_path, bbox):
    f = write(tmp_path, "a.geojson", [])
    with pytest.raises(ValueError):
        select_events([f], D(1), D(2), 4.0, bbox=bbox)


def test_invalid_period(tmp_path):
    f = write(tmp_path, "a.geojson", [])
    with pytest.raises(ValueError):
        select_events([f], D(2), D(2), 4.0)


def test_duplicate_keeps_greater_updated(tmp_path):
    f1 = write(tmp_path, "a.geojson", [feat("a", MS(1), 5, updated=10)])
    f2 = write(tmp_path, "b.geojson", [feat("a", MS(1), 6, updated=20)])
    for files in ([f1, f2], [f2, f1]):
        sel = select_events(files, D(1), D(2), 4.0)
        assert len(sel.features) == 1
        assert sel.features[0]["properties"]["updated"] == 20


def test_order_by_time_then_id_and_features_untouched(tmp_path):
    original = [feat("z", MS(1, 5), 5), feat("b", MS(1, 1), 5), feat("a", MS(1, 1), 5)]
    f = write(tmp_path, "a.geojson", json.loads(json.dumps(original)))
    sel = select_events([f], D(1), D(2), 4.0)
    assert [x["id"] for x in sel.features] == ["a", "b", "z"]
    assert sel.features[2] == original[0]


def test_empty_selection(tmp_path):
    f = write(tmp_path, "a.geojson", [feat("a", MS(5), 5)])
    sel = select_events([f], D(1), D(2), 4.0)
    assert sel.features == [] and sel.count == 0
    assert sel.first_time_ms is None
    assert len(sel.content_sha256) == 64


def test_fingerprint_stable_and_sensitive(tmp_path):
    f = write(tmp_path, "a.geojson", [feat("a", MS(1), 5, updated=1), feat("b", MS(1, 1), 5, updated=2)])
    g = write(tmp_path, "b.geojson", [feat("b", MS(1, 1), 5, updated=2), feat("a", MS(1), 5, updated=1)])
    h = write(tmp_path, "c.geojson", [feat("a", MS(1), 5, updated=1), feat("b", MS(1, 1), 5, updated=3)])
    s1 = select_events([f], D(1), D(2), 4.0)
    assert s1.content_sha256 == select_events([g], D(1), D(2), 4.0).content_sha256
    assert s1.content_sha256 != select_events([h], D(1), D(2), 4.0).content_sha256


def test_unreadable_file(tmp_path):
    bad = tmp_path / "bad.geojson"
    bad.write_text("no json", encoding="utf-8")
    with pytest.raises(ValueError):
        select_events([bad], D(1), D(2), 4.0)
