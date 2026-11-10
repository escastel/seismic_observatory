"""Parameterized SQL queries for API endpoints."""

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
        add("g.country = ?", filters.country)
    if filters.date_from is not None:
        add("f.event_time >= ?", filters.date_from)
    if filters.date_to is not None:
        add("f.event_time <= ?", filters.date_to)
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
        SELECT f.external_id AS id, f.updated, f.event_time AS time,
               f.magnitude AS mag, f.place, f.longitude, f.latitude, f.depth_km,
               g.country, g.continent, g.subregion, f.source_topic
        FROM fact_sismos f
        JOIN dim_geografia g ON g.geografia_key = f.geografia_key
        {where}
        ORDER BY f.event_time DESC, f.external_id
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
            FROM fact_sismos f
            JOIN dim_geografia g ON g.geografia_key = f.geografia_key
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
        SELECT g.country, COUNT(*)::int AS count
        FROM fact_sismos f
        JOIN dim_geografia g ON g.geografia_key = f.geografia_key
        {where}
        GROUP BY g.country
        ORDER BY count DESC, g.country
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
        FROM fact_sismos f
        JOIN dim_geografia g ON g.geografia_key = f.geografia_key
        {where}
        GROUP BY period
        ORDER BY period
        """,
        *values,
    )
