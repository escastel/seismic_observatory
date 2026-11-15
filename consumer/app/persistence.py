"""Writes of one Kafka message, inside the caller's transaction.

Follows contracts/database.md, «Transacción del consumidor por mensaje»: the
event goes through apply_event_version (or the rejection into quarantine) and
the message_log row is written in the same transaction. The services never
run DDL: the model is created by db/sql/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from .quality import ValidatedEvent

APPLY_SQL = """
SELECT apply_event_version($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, $15, $16, $17)
"""

QUARANTINE_SQL = """
INSERT INTO quarantine (kafka_topic, kafka_partition, kafka_offset, event_id,
                        reason_codes, reason_detail, payload, raw_text)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING
"""

MESSAGE_LOG_SQL = """
INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, event_id, updated_at, outcome, produced_at)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING
"""


@dataclass(frozen=True)
class Position:
    """Where a message sits in Kafka."""

    topic: str
    partition: int
    offset: int


@dataclass(frozen=True)
class Rejection:
    """A message that goes to quarantine, with every reason found."""

    reason_codes: list[str]
    reason_detail: str
    event_id: str | None = None
    payload: Any = None          # decoded JSON, when the message was JSON
    raw_text: str | None = None  # original text, when it was not


def to_json(value: Any) -> str:
    """Strict JSON (no NaN or infinity), as PostgreSQL jsonb requires."""
    return json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"))


async def store_version(
    conn: asyncpg.Connection,
    position: Position,
    event: ValidatedEvent,
    *,
    source: str,
    country_id: str | None,
    original: Any,
    replayed_at: datetime | None,
) -> str:
    """apply_event_version; returns new, revised, stale or duplicate."""
    return await conn.fetchval(
        APPLY_SQL,
        event.external_id,
        source,
        event.event_time,
        event.updated,
        event.magnitude,
        event.mag_type,
        event.longitude,
        event.latitude,
        event.depth_km,
        event.place or None,
        country_id,
        [],
        to_json(original),
        position.topic,
        position.partition,
        position.offset,
        replayed_at,
    )


async def store_rejection(conn: asyncpg.Connection, position: Position, rejection: Rejection) -> str:
    """Quarantine row, once per message position; returns 'quarantined'."""
    await conn.execute(
        QUARANTINE_SQL,
        position.topic,
        position.partition,
        position.offset,
        rejection.event_id,
        rejection.reason_codes,
        rejection.reason_detail,
        to_json(rejection.payload) if rejection.raw_text is None else None,
        rejection.raw_text,
    )
    return "quarantined"


async def log_message(
    conn: asyncpg.Connection,
    position: Position,
    *,
    outcome: str,
    event_id: str | None,
    updated_at: datetime | None,
    produced_at: datetime | None,
) -> None:
    await conn.execute(
        MESSAGE_LOG_SQL,
        position.topic,
        position.partition,
        position.offset,
        event_id,
        updated_at,
        outcome,
        produced_at,
    )
