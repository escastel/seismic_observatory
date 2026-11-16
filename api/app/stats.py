"""Statistics derived from the current state of events (constitution VII).

Nothing is kept incrementally: every figure is computed from event_current with the same
WHERE builder as the map. Hourly windows are fixed UTC hours, end excluded.
"""

from __future__ import annotations

import calendar
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from .filters import ParameterError, QueryFilters, build_where
from .queries import count_total
from .serialize import to_ms

MAX_WINDOWS = 10000
HOUR_MS = 3_600_000
NO_COUNTRY_LABEL = "Sin país asignado"
EPOCH_SQL = "TIMESTAMPTZ '2000-01-01 00:00:00+00'"  # aligns date_bin to whole UTC hours

DEPTH_BINS: list[tuple[int, str, float | None, float | None]] = [
    (0, "<0", None, 0.0),
    (1, "0-70", 0.0, 70.0),
    (2, "70-300", 70.0, 300.0),
    (3, ">=300", 300.0, None),
]


def _floor_hour_ms(instant: datetime) -> int:
    return to_ms(instant) // HOUR_MS * HOUR_MS


async def hourly_counts(
    conn: asyncpg.Connection, filters: QueryFilters, now: datetime
) -> tuple[dict[str, Any], list[dict[str, int]]]:
    """Counts per fixed UTC hour over the effective period, empty hours included as 0.

    Returns the effective period and the windows. More than MAX_WINDOWS windows is a
    client error (narrow the period); the answer is never truncated.
    """
    where = build_where(filters, now)
    low, high = await conn.fetchrow(
        f"SELECT min(f.event_time), max(f.event_time) FROM event_current f {where.sql}", *where.values
    )
    start = where.period_start or low
    end = where.period_end
    if end is None and high is not None:
        end = high + timedelta(milliseconds=1)
        if filters.mode == "live":
            end = max(end, now)
    period = {
        "start": to_ms(start) if start else None,
        "end": to_ms(end) if end else None,
        "default_applied": where.default_applied,
    }
    if start is None or end is None:
        return period, []

    first = _floor_hour_ms(start)
    last = _floor_hour_ms(end - timedelta(microseconds=1))
    windows = (last - first) // HOUR_MS + 1
    if windows > MAX_WINDOWS:
        raise ParameterError(
            "start", f"the period has {windows} hourly windows; narrow it to at most {MAX_WINDOWS} hours"
        )

    n = len(where.values)
    rows = await conn.fetch(
        f"""
        SELECT g.w AS start, COALESCE(c.n, 0)::int AS count
        FROM generate_series(
                 date_bin('1 hour', ${n + 1}::timestamptz, {EPOCH_SQL}),
                 date_bin('1 hour', ${n + 2}::timestamptz - interval '1 microsecond', {EPOCH_SQL}),
                 interval '1 hour') AS g(w)
        LEFT JOIN (
            SELECT date_bin('1 hour', f.event_time, {EPOCH_SQL}) AS w, count(*) AS n
            FROM event_current f {where.sql}
            GROUP BY 1
        ) c ON c.w = g.w
        ORDER BY g.w
        """,
        *where.values,
        start,
        end,
    )
    return period, [{"start": to_ms(row["start"]), "count": row["count"]} for row in rows]


async def counts_by_country(conn: asyncpg.Connection, filters: QueryFilters, now: datetime) -> list[dict[str, Any]]:
    where = build_where(filters, now)
    rows = await conn.fetch(
        f"""
        SELECT f.country_id, g.name_es AS country_name, count(*)::int AS count
        FROM event_current f
        LEFT JOIN core.dim_country g ON g.country_id = f.country_id
        {where.sql}
        GROUP BY f.country_id, g.name_es
        ORDER BY count DESC, f.country_id NULLS LAST
        """,
        *where.values,
    )
    return [
        {
            "country_id": row["country_id"],
            "country_name": row["country_name"] or NO_COUNTRY_LABEL,
            "count": row["count"],
        }
        for row in rows
    ]


async def magnitude_distribution(conn: asyncpg.Connection, filters: QueryFilters, now: datetime) -> dict[str, Any]:
    """One-unit bins by floor(magnitude), negatives included; null magnitudes counted apart."""
    where = build_where(filters, now)
    rows = await conn.fetch(
        f"""
        SELECT floor(f.magnitude)::int AS bin, count(*)::int AS count
        FROM event_current f {where.sql}
        GROUP BY 1
        """,
        *where.values,
    )
    unvalued = sum(row["count"] for row in rows if row["bin"] is None)
    counts = {row["bin"]: row["count"] for row in rows if row["bin"] is not None}
    items: list[dict[str, Any]] = []
    if counts:
        for low in range(min(counts), max(counts) + 1):
            items.append({"from": low, "to": low + 1, "count": counts.get(low, 0)})
    return {"unit": "magnitude, 1 unit bins [from, to)", "items": items, "unvalued": unvalued}


async def depth_distribution(conn: asyncpg.Connection, filters: QueryFilters, now: datetime) -> dict[str, Any]:
    where = build_where(filters, now)
    rows = await conn.fetch(
        f"""
        SELECT CASE WHEN f.depth_km IS NULL THEN NULL
                    WHEN f.depth_km < 0 THEN 0
                    WHEN f.depth_km < 70 THEN 1
                    WHEN f.depth_km < 300 THEN 2
                    ELSE 3 END AS bin,
               count(*)::int AS count
        FROM event_current f {where.sql}
        GROUP BY 1
        """,
        *where.values,
    )
    counts = {row["bin"]: row["count"] for row in rows}
    items = [
        {"label": label, "from": low, "to": high, "count": counts.get(index, 0)}
        for index, label, low, high in DEPTH_BINS
    ]
    return {"unit": "km", "items": items, "unvalued": counts.get(None, 0)}


async def comparison_counts(
    conn: asyncpg.Connection, filters: QueryFilters, now: datetime, baseline_year: int
) -> dict[str, Any]:
    """Raw counts of the last 24 hours and of the baseline year, with the same filters.

    min_mag, country_id, exclude_synthetic and mode apply to both periods; start and end
    define the main period only. The anchor of the recent window is end, else now (live) or
    the latest replayed event (replay).
    """
    base = replace(filters, start=None, end=None)
    anchor = filters.end
    if anchor is None:
        if filters.mode == "live":
            anchor = now
        else:
            where = build_where(base, now)
            latest = await conn.fetchval(f"SELECT max(f.event_time) FROM event_current f {where.sql}", *where.values)
            anchor = latest + timedelta(milliseconds=1) if latest else now
    recent_start = anchor - timedelta(hours=24)
    year_start = datetime(baseline_year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(baseline_year + 1, 1, 1, tzinfo=timezone.utc)
    recent = await count_total(conn, build_where(replace(base, start=recent_start, end=anchor), now))
    baseline = await count_total(conn, build_where(replace(base, start=year_start, end=year_end), now))
    return {
        "recent": {"start": to_ms(recent_start), "end": to_ms(anchor), "count": recent},
        "baseline_events": baseline,
        "year": baseline_year,
        "anchor_is_data": filters.end is None and filters.mode == "replay",
    }


def compare(recent_count: int, baseline_events: int, year: int, *, anchor_is_data: bool = False) -> dict[str, Any]:
    """Compare the recent period with the baseline year.

    The denominator is the number of days of the year, including days without events.
    """
    days = 366 if calendar.isleap(year) else 365
    daily_mean = baseline_events / days
    warning = "El periodo reciente puede estar incompleto: USGS añade y revisa eventos durante horas."
    if anchor_is_data:
        warning += " La referencia se ha calculado solo sobre los datos reproducidos."
    return {
        "baseline": {"year": year, "events": baseline_events, "days": days, "daily_mean": daily_mean},
        "ratio": recent_count / daily_mean if daily_mean else "ND",
        "filters_applied": ["min_mag", "country_id", "exclude_synthetic"],
        "warning": warning,
    }
