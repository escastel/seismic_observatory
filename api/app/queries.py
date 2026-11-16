"""Parameterized SQL queries for API endpoints.

They read event_current with the search_path of the pool (core for live
data), joined to dim_country; a NULL country_id means «Sin país asignado».
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

import asyncpg

from .schemas import EventFilters


def _event_conditions(filters: EventFilters) -> tuple[list[str], list[Any]]:
    conditions: list[str] = []
    values: list[Any] = []

    def add(condition: str, value: Any) -> None:
        values.append(value)
        conditions.append(condition.replace("?", f"${len(values)}"))

    if filters.country is not None:
        add("g.name_es = ?", filters.country)
    if filters.country_id is not None:
        add("f.country_id = ?", filters.country_id)
    if filters.date_from is not None:
        add("f.event_time >= ?", filters.date_from)
    if filters.date_to is not None:
        add(
            "f.event_time < ?" if filters.end_exclusive else "f.event_time <= ?",
            filters.date_to,
        )
    if filters.min_magnitude is not None:
        add("f.magnitude >= ?", filters.min_magnitude)
    if filters.max_magnitude is not None:
        add("f.magnitude <= ?", filters.max_magnitude)
    return conditions, values


async def fetch_events(pool: asyncpg.Pool, filters: EventFilters) -> list[asyncpg.Record]:
    conditions, values = _event_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_index = len(values) + 1
    offset_index = len(values) + 2
    values.extend([filters.limit, filters.offset])
    return await pool.fetch(
        f"""
        SELECT f.event_id AS id, f.updated_at AS updated, f.event_time AS time,
               f.magnitude AS mag, f.mag_type, f.place, f.longitude, f.latitude, f.depth_km,
               g.name_es AS country, g.name_es AS country_name, g.continent, g.subregion, f.country_id,
               f.source
        FROM event_current f
        LEFT JOIN dim_country g ON g.country_id = f.country_id
        {where}
        ORDER BY f.event_time DESC, f.event_id
        LIMIT ${limit_index} OFFSET ${offset_index}
        """,
        *values,
    )


async def count_events(pool: asyncpg.Pool, filters: EventFilters) -> int:
    conditions, values = _event_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return int(
        await pool.fetchval(
            f"""
            SELECT COUNT(*)
            FROM event_current f
            LEFT JOIN dim_country g ON g.country_id = f.country_id
            {where}
            """,
            *values,
        )
    )


async def country_stats(pool: asyncpg.Pool, filters: EventFilters) -> list[asyncpg.Record]:
    conditions, values = _event_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return await pool.fetch(
        f"""
        SELECT g.name_es AS country, COUNT(*)::int AS count
        FROM event_current f
        LEFT JOIN dim_country g ON g.country_id = f.country_id
        {where}
        GROUP BY g.name_es
        ORDER BY count DESC, g.name_es NULLS LAST
        """,
        *values,
    )


async def timeline_stats(
    pool: asyncpg.Pool,
    filters: EventFilters,
    bucket: str,
) -> list[asyncpg.Record]:
    conditions, values = _event_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    expression = {
        "day": "date_trunc('day', f.event_time)",
        "week": "date_trunc('week', f.event_time)",
        "month": "date_trunc('month', f.event_time)",
    }[bucket]
    return await pool.fetch(
        f"""
        SELECT {expression} AS period, COUNT(*)::int AS count
        FROM event_current f
        LEFT JOIN dim_country g ON g.country_id = f.country_id
        {where}
        GROUP BY period
        ORDER BY period
        """,
        *values,
    )


async def magnitude_stats(
    pool: asyncpg.Pool,
    filters: EventFilters,
) -> list[asyncpg.Record]:
    conditions, values = _event_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return await pool.fetch(
        f"""
        SELECT COALESCE(f.magnitude::text, 'null') AS bucket, COUNT(*)::int AS count
        FROM event_current f
        LEFT JOIN dim_country g ON g.country_id = f.country_id
        {where}
        GROUP BY bucket
        ORDER BY bucket
        """,
        *values,
    )


async def depth_stats(
    pool: asyncpg.Pool,
    filters: EventFilters,
) -> list[asyncpg.Record]:
    conditions, values = _event_conditions(filters)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return await pool.fetch(
        f"""
        SELECT CASE WHEN f.depth_km IS NULL THEN 'unknown'
               WHEN f.depth_km < 70 THEN 'shallow'
               WHEN f.depth_km < 300 THEN 'intermediate'
               ELSE 'deep' END AS bucket, COUNT(*)::int AS count
        FROM event_current f
        LEFT JOIN dim_country g ON g.country_id = f.country_id
        {where}
        GROUP BY bucket
        ORDER BY bucket
        """,
        *values,
    )


async def daily_average_2025(
    pool: asyncpg.Pool,
    filters: EventFilters,
) -> float:
    conditions, values = _event_conditions(filters)
    conditions.append("EXTRACT(YEAR FROM f.event_time) = 2025")
    where = f"WHERE {' AND '.join(conditions)}"
    value = await pool.fetchval(
        f"""
        SELECT COALESCE(AVG(day_count), 0) FROM (
            SELECT DATE_TRUNC('day', f.event_time), COUNT(*)::numeric AS day_count
            FROM event_current f
            LEFT JOIN dim_country g ON g.country_id = f.country_id
            {where}
            GROUP BY DATE_TRUNC('day', f.event_time)
        ) daily
        """,
        *values,
    )
    return float(value or 0)


async def missing_magnitude(
    pool: asyncpg.Pool,
    filters: EventFilters,
) -> int:
    conditions, values = _event_conditions(filters)
    conditions.append("f.magnitude IS NULL")
    where = f"WHERE {' AND '.join(conditions)}"
    return int(
        await pool.fetchval(
            f"""
            SELECT COUNT(*)
            FROM event_current f
            LEFT JOIN dim_country g ON g.country_id = f.country_id
            {where}
            """,
            *values,
        )
    )
