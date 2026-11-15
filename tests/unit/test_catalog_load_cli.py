"""Arguments of the catalog-loader command (contracts/catalog-loader.md, FR-018)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from producer.app.catalog import Filters, Interval, file_name
from producer.app.catalog_load import UsageError, main, parse_request

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_defaults_are_the_mandatory_2025_load() -> None:
    request = parse_request([], NOW)

    assert (request.start, request.end) == (utc(2025, 1, 1), utc(2026, 1, 1))
    assert request.filters == Filters(4.0, "earthquake")
    assert request.purpose == "historical_load"
    assert (request.refresh, request.dry_run, request.list_gaps) == (False, False, False)


def test_2026_extension_keeps_the_filter() -> None:
    request = parse_request(["--start", "2026-01-01", "--end", "2026-11-15"], NOW)

    assert (request.start, request.end) == (utc(2026, 1, 1), utc(2026, 11, 15))
    assert request.filters == Filters(4.0, "earthquake")


def test_gap_recovery_uses_every_magnitude_and_type() -> None:
    request = parse_request(
        ["--purpose", "gap_recovery", "--start", "2026-11-12T09:00:00Z", "--end", "2026-11-13T22:00:00Z"], NOW
    )

    assert request.purpose == "gap_recovery"
    assert request.filters == Filters(None, None)
    assert (request.start, request.end) == (utc(2026, 11, 12, 9), utc(2026, 11, 13, 22))


@pytest.mark.parametrize(
    "argv",
    [
        ["--purpose", "gap_recovery"],
        ["--purpose", "gap_recovery", "--start", "2026-11-12"],
        ["--start", "2025-03-01", "--end", "2025-03-01"],
        ["--start", "2025-03-01", "--end", "2025-02-01"],
        ["--start", "2026-11-01", "--end", "2026-11-16"],
        ["--start", "yesterday"],
        ["--purpose", "backfill"],
        ["--min-magnitude", "four"],
    ],
    ids=["gap-no-dates", "gap-no-end", "empty", "reversed", "future", "unreadable", "bad-purpose", "bad-magnitude"],
)
def test_invalid_arguments_are_usage_errors(argv) -> None:
    with pytest.raises(UsageError):
        parse_request(argv, NOW)


def test_main_returns_2_without_touching_anything(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("must not read settings or connect")

    monkeypatch.setattr("producer.app.catalog_load.load_settings", boom)
    assert main(["--start", "2025-03-01", "--end", "2025-02-01"]) == 2


def test_filter_switches() -> None:
    assert parse_request(["--all-magnitudes"], NOW).filters == Filters(None, "earthquake")
    assert parse_request(["--all-types"], NOW).filters == Filters(4.0, None)
    assert parse_request(["--min-magnitude", "2.5", "--event-type", "explosion"], NOW).filters == Filters(2.5, "explosion")


def test_other_switches() -> None:
    assert parse_request(["--refresh"], NOW).refresh
    assert parse_request(["--dry-run"], NOW).dry_run
    assert parse_request(["--gaps"], NOW).list_gaps


def test_naive_dates_are_utc() -> None:
    assert parse_request(["--start", "2025-06-01T12:30:00", "--end", "2025-07-01"], NOW).start == utc(2025, 6, 1, 12, 30)


def test_file_names() -> None:
    month = Interval(utc(2025, 1, 1), utc(2025, 2, 1))
    assert file_name(month, Filters(4.0, "earthquake")) == "2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake.geojson"
    assert file_name(month, Filters(None, None)) == "2025-01-01T000000Z_2025-02-01T000000Z_all.geojson"
    assert file_name(month, Filters(2.5, None)) == "2025-01-01T000000Z_2025-02-01T000000Z_m2.5.geojson"
    assert file_name(month, Filters(4.0, "earthquake"), "9b2d8cb824cb0123") == (
        "2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake_9b2d8cb824cb.geojson")
