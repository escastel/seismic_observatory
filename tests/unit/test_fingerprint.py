"""Content fingerprints (FR-004, research R3)."""

from __future__ import annotations

import hashlib

from producer.app.fingerprint import bytes_fingerprint, canonical_json, features_fingerprint, file_fingerprint
from tests.support.usgs_stub import collection, feature


def test_key_order_does_not_change_the_fingerprint() -> None:
    a = [{"id": "E1", "properties": {"mag": 4.2, "time": 1}}]
    b = [{"properties": {"time": 1, "mag": 4.2}, "id": "E1"}]
    assert features_fingerprint(a) == features_fingerprint(b)


def test_any_value_or_order_change_does() -> None:
    base = [feature("E1"), feature("E2")]
    changed = [feature("E1", mag=4.3), feature("E2")]
    reordered = [feature("E2"), feature("E1")]
    assert features_fingerprint(base) != features_fingerprint(changed)
    assert features_fingerprint(base) != features_fingerprint(reordered)


def test_metadata_is_not_part_of_the_fingerprint() -> None:
    events = [feature("E1")]
    first = collection(events, generated=1)
    second = collection(events, generated=2)
    assert first != second
    assert features_fingerprint(first["features"]) == features_fingerprint(second["features"])


def test_canonical_json_is_compact_utf8() -> None:
    assert canonical_json({"b": 1, "a": "ñ"}) == '{"a":"ñ","b":1}'.encode()


def test_bytes_and_file_fingerprints_match_sha256(tmp_path) -> None:
    data = b'{"type":"FeatureCollection"}' * 100_000
    path = tmp_path / "catalog.geojson"
    path.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert bytes_fingerprint(data) == expected
    assert file_fingerprint(path) == expected
