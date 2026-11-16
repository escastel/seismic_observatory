"""Monthly intervals and subdivision without truncation (FR-019, research R8)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from producer.app.catalog import Filters, Interval, IntervalTooLarge, iso, month_intervals, plan_intervals


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_year_2025_is_twelve_contiguous_months() -> None:
    months = month_intervals(utc(2025, 1, 1), utc(2026, 1, 1))

    assert len(months) == 12
    assert months[0] == Interval(utc(2025, 1, 1), utc(2025, 2, 1))
    assert months[-1] == Interval(utc(2025, 12, 1), utc(2026, 1, 1))
    assert all(a.end == b.start for a, b in zip(months, months[1:]))


def test_partial_first_and_last_months() -> None:
    months = month_intervals(utc(2026, 9, 15, 6), utc(2026, 11, 3))

    assert months == [
        Interval(utc(2026, 9, 15, 6), utc(2026, 10, 1)),
        Interval(utc(2026, 10, 1), utc(2026, 11, 1)),
        Interval(utc(2026, 11, 1), utc(2026, 11, 3)),
    ]


def test_period_inside_one_month() -> None:
    assert month_intervals(utc(2026, 11, 12, 9), utc(2026, 11, 13, 22)) == [Interval(utc(2026, 11, 12, 9), utc(2026, 11, 13, 22))]


def test_empty_period_is_rejected() -> None:
    with pytest.raises(ValueError):
        month_intervals(utc(2025, 2, 1), utc(2025, 2, 1))


def counter(density_per_day: float, hot: Interval | None = None, hot_density: float = 0.0, max_allowed: int = 100):
    """Fake /count: events spread evenly, optionally with a denser stretch."""
    calls: list[Interval] = []

    async def count(interval: Interval) -> tuple[int, int]:
        calls.append(interval)
        days = (interval.end - interval.start).total_seconds() / 86400
        n = days * density_per_day
        if hot is not None:
            overlap = (min(interval.end, hot.end) - max(interval.start, hot.start)).total_seconds() / 86400
            n += max(0.0, overlap) * hot_density
        return round(n), max_allowed

    return count, calls


def plan(interval: Interval, count):
    return asyncio.run(plan_intervals(interval, count))


def test_interval_under_the_limit_is_kept_whole() -> None:
    count, calls = counter(density_per_day=2)
    month = Interval(utc(2025, 1, 1), utc(2025, 2, 1))

    assert plan(month, count) == [(month, 62)]
    assert calls == [month]


def test_interval_over_the_limit_is_halved_recursively() -> None:
    month = Interval(utc(2025, 7, 1), utc(2025, 8, 1))
    hot = Interval(utc(2025, 7, 29), utc(2025, 7, 30))
    count, _ = counter(density_per_day=2, hot=hot, hot_density=300)

    parts = plan(month, count)

    assert all(declared <= 100 for _, declared in parts)
    assert len(parts) > 2
    assert parts[0][0].start == month.start and parts[-1][0].end == month.end
    assert all(a.end == b.start for (a, _), (b, _) in zip(parts, parts[1:]))
    assert sum(declared for _, declared in parts) >= 300


def test_split_points_are_whole_seconds() -> None:
    count, _ = counter(density_per_day=1000)
    parts = plan(Interval(utc(2025, 1, 1), utc(2025, 1, 2)), count)
    assert len(parts) > 1
    assert all(part.start.microsecond == 0 and part.end.microsecond == 0 for part, _ in parts)


def test_interval_that_cannot_be_split_further_is_an_error() -> None:
    async def count(interval: Interval) -> tuple[int, int]:
        return 500, 100  # every interval, however small, exceeds the maximum

    with pytest.raises(IntervalTooLarge, match="cannot be split"):
        plan(Interval(utc(2025, 1, 1), utc(2025, 1, 2)), count)


def test_instants_are_formatted_for_usgs() -> None:
    assert iso(utc(2025, 1, 1)) == "2025-01-01T00:00:00Z"
    assert iso(utc(2026, 11, 12, 9, 5, 7)) == "2026-11-12T09:05:07Z"


def test_filters_build_usgs_parameters() -> None:
    month = Interval(utc(2025, 1, 1), utc(2025, 2, 1))
    assert Filters(4.0, "earthquake").query_params(month) == {
        "format": "geojson",
        "starttime": "2025-01-01T00:00:00Z",
        "endtime": "2025-02-01T00:00:00Z",
        "minmagnitude": 4,
        "eventtype": "earthquake",
        "orderby": "time-asc",
    }
    assert Filters(None, None).count_params(month) == {
        "format": "geojson",
        "starttime": "2025-01-01T00:00:00Z",
        "endtime": "2025-02-01T00:00:00Z",
    }
    assert "limit" not in Filters(2.5, None).query_params(month)
    assert Filters(2.5, None).query_params(month)["minmagnitude"] == 2.5


def test_interval_length() -> None:
    assert Interval(utc(2025, 1, 1), utc(2025, 1, 2)).seconds == timedelta(days=1).total_seconds()
