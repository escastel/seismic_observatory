"""Parameterized SQL of the event endpoint and the metadata around it.

Statements are unqualified (event_current, quarantine): the search_path of the pool decides
whether they read core (live) or replay. The only qualified table is core.extraction, which
exists only in core. Every value is a bound parameter.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import asyncpg

from .filters import SYNTHETIC_SQL, Where

# Quarantine reason codes (consumer/app/rules.py) that mean «no valid point».
GEOMETRY_REASONS = [
    "geometry_missing",
    "geometry_not_point",
    "coordinates_missing",
    "coordinates_not_numeric",
    "coordinates_not_finite",
    "coordinates_out_of_range",
]

LAST_INGESTION_SQL = """
    SELECT max(requested_at)
    FROM core.extraction
    WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')
"""


@asynccontextmanager
async def snapshot(pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    """One read-only snapshot: every query of a response sees the same state."""
    async with pool.acquire() as conn:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            yield conn


def _and(where: Where, condition: str) -> str:
    return f"{where.sql} AND {condition}" if where.sql else f"WHERE {condition}"


async def fetch_page(
    conn: asyncpg.Connection, where: Where, limit: int, offset: int, *, replay: bool
) -> list[asyncpg.Record]:
    extra = f", f.replayed_at, {SYNTHETIC_SQL} AS is_synthetic" if replay else ""
    values: list[Any] = [*where.values, limit, offset]
    return await conn.fetch(
        f"""
        SELECT f.event_id AS id, f.updated_at AS updated, f.event_time AS time,
               f.magnitude AS mag, f.mag_type, f.place, f.longitude, f.latitude, f.depth_km,
               f.country_id, g.name_es AS country_name, g.continent, g.subregion{extra}
        FROM event_current f
        LEFT JOIN core.dim_country g ON g.country_id = f.country_id
        {where.sql}
        ORDER BY f.event_time DESC, f.event_id ASC
        LIMIT ${len(where.values) + 1} OFFSET ${len(where.values) + 2}
        """,
        *values,
    )


async def count_total(conn: asyncpg.Connection, where: Where) -> int:
    return int(await conn.fetchval(f"SELECT count(*) FROM event_current f {where.sql}", *where.values))


async def count_null_magnitude(conn: asyncpg.Connection, where_without_min_mag: Where) -> int:
    """Events with a null magnitude that satisfy every filter except min_mag."""
    sql = f"SELECT count(*) FROM event_current f {_and(where_without_min_mag, 'f.magnitude IS NULL')}"
    return int(await conn.fetchval(sql, *where_without_min_mag.values))


async def quarantine_counts(conn: asyncpg.Connection) -> dict[str, int]:
    """Non-synthetic quarantined messages of the schema of the pool; geometry subset apart."""
    row = await conn.fetchrow(
        """
        SELECT count(*)::int AS total,
               (count(*) FILTER (WHERE reason_codes && $1::text[]))::int AS invalid_geometry
        FROM quarantine
        WHERE NOT is_synthetic
        """,
        GEOMETRY_REASONS,
    )
    return {"total": row["total"], "invalid_geometry": row["invalid_geometry"]}


async def last_ingestion(conn: asyncpg.Connection) -> datetime | None:
    """Last correct query to the USGS feed, registered by the producer. Always from core."""
    return await conn.fetchval(LAST_INGESTION_SQL)


async def last_replayed_at(conn: asyncpg.Connection) -> datetime | None:
    return await conn.fetchval("SELECT max(replayed_at) FROM event_current")
