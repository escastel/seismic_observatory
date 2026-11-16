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

from .rules import Exclusion, Quarantine, ValidatedEvent

APPLY_SQL = """
SELECT apply_event_version($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, $15, $16, $17)
"""

QUARANTINE_SQL = """
INSERT INTO quarantine (kafka_topic, kafka_partition, kafka_offset, event_id,
                        reason_codes, reason_detail, payload, raw_text, is_synthetic)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING
"""

# The extraction is linked only when it exists: the foreign key must not fail a message.
EXCLUDED_SQL = """
INSERT INTO excluded_event (event_id, updated_at, event_type, reason_code, extraction_id, payload)
VALUES ($1, $2, $3, $4, (SELECT extraction_id FROM core.extraction WHERE extraction_id = $5), $6::jsonb)
ON CONFLICT (event_id, updated_at) DO NOTHING
"""

MESSAGE_LOG_SQL = """
INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, event_id, updated_at, outcome, produced_at)
VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset, attempt) DO NOTHING
"""


@dataclass(frozen=True)
class Position:
    """Where a message sits in Kafka."""

    topic: str
    partition: int
    offset: int


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
    flags: list[str],
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
        flags,
        to_json(original),
        position.topic,
        position.partition,
        position.offset,
        replayed_at,
    )


async def store_rejection(conn: asyncpg.Connection, position: Position, rejection: Quarantine) -> str:
    """Quarantine row, once per message position; returns 'quarantined'."""
    payload, raw_text = None, rejection.raw_text
    if raw_text is None:
        try:
            payload = to_json(rejection.payload)
        except ValueError:
            # A literal like 1e999 decodes to infinity, which jsonb cannot hold: keep the text.
            raw_text = json.dumps(rejection.payload, ensure_ascii=False)
    await conn.execute(
        QUARANTINE_SQL,
        position.topic,
        position.partition,
        position.offset,
        rejection.event_id,
        rejection.reasons,
        rejection.detail,
        payload,
        raw_text,
        rejection.synthetic,
    )
    return "quarantined"


async def store_exclusion(conn: asyncpg.Connection, exclusion: Exclusion, extraction_id: int | None) -> str:
    """excluded_event row (once per event version); returns 'excluded'."""
    await conn.execute(
        EXCLUDED_SQL,
        exclusion.event_id,
        exclusion.updated_at,
        exclusion.event_type,
        exclusion.reason_code,
        extraction_id,
        to_json(exclusion.feature),
    )
    return "excluded"


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
