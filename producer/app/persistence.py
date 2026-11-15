"""Durable producer publication state (core.publish_state).

The table belongs to the data model (db/sql/040_event_tables.sql); the
producer only reads and writes rows, as observatory_writer.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

import asyncpg

PUBLISHED_SQL = "SELECT event_id, updated_at FROM publish_state WHERE event_id = ANY($1::text[])"

# contracts/database.md, «Estado de publicación»: never moves back.
MARK_SQL = """
INSERT INTO publish_state (event_id, updated_at)
VALUES ($1, $2)
ON CONFLICT (event_id) DO UPDATE
SET updated_at = EXCLUDED.updated_at, published_at = now()
WHERE EXCLUDED.updated_at > publish_state.updated_at
"""


async def published_versions(conn: asyncpg.Connection, event_ids: Iterable[str]) -> dict[str, datetime]:
    """Last version confirmed by Kafka for each of the given events."""
    rows = await conn.fetch(PUBLISHED_SQL, list(event_ids))
    return {row["event_id"]: row["updated_at"] for row in rows}


def should_publish(published: dict[str, datetime], event_id: str, updated: datetime) -> bool:
    current = published.get(event_id)
    return current is None or updated > current


async def mark_published(conn: asyncpg.Connection, event_id: str, updated: datetime) -> None:
    """Record a version after Kafka confirmed it."""
    await conn.execute(MARK_SQL, event_id, updated)
