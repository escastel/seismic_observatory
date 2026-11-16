"""Sorting of USGS items into earthquakes, exclusions and unidentifiable (FR-003, FR-010, FR-011)."""

from __future__ import annotations

from datetime import datetime, timezone

from producer.app.classify import classify, millis_to_utc
from tests.support.usgs_stub import feature


def test_one_item_of_each_kind() -> None:
    no_id = feature(None)
    bad_updated = feature("E9")
    bad_updated["properties"]["updated"] = "yesterday"
    items = [
        feature("E1"),
        feature("Q1", event_type="quarry blast"),
        feature("X1", event_type=None),
        no_id,
        bad_updated,
        "not a feature",
    ]

    result = classify(items)

    assert [item.event_id for item in result.earthquakes] == ["E1"]
    assert [(e.item.event_id, e.item.event_type, e.reason_code) for e in result.excluded] == [
        ("Q1", "quarry blast", "not_earthquake"),
        ("X1", None, "missing_type"),
    ]
    assert [u.position for u in result.unidentifiable] == [3, 4, 5]
    assert result.received == len(items) == 6
    assert len(result.earthquakes) + result.excluded_count == result.received


def test_updated_is_converted_to_utc() -> None:
    item = classify([feature("E1", time="2026-11-14T10:00:00Z", updated="2026-11-14T10:05:00Z")]).earthquakes[0]
    assert item.updated_at == datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)
    assert item.position == 0


def test_unidentifiable_detail_names_positions() -> None:
    result = classify([feature("E1"), feature(None)])
    assert result.unidentifiable_detail() == "1 unidentifiable item(s) counted as excluded (#1: no id)"
    assert classify([feature("E1")]).unidentifiable_detail() is None


def test_blank_id_is_unidentifiable() -> None:
    assert classify([feature("  ")]).unidentifiable[0].reason == "no id"


def test_millis_to_utc_rejects_what_is_not_a_number() -> None:
    assert millis_to_utc(0) == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert millis_to_utc("1735689600000") == datetime(2025, 1, 1, tzinfo=timezone.utc)
    for value in (None, True, "soon", [1], 1e30):
        assert millis_to_utc(value) is None


def test_empty_response() -> None:
    result = classify([])
    assert (result.received, result.excluded_count) == (0, 0)
