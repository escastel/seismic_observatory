"""SQL helpers shared by the data model tests.

They issue exactly the statements described in
specs/002-platform-data-model/contracts/database.md, so the tests exercise the
contract the services rely on rather than private details of the SQL files.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


def utc(text: str) -> datetime:
    """Parse '2026-11-14 10:05' (or an ISO string with offset) as an aware datetime."""
    value = datetime.fromisoformat(text)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass
class Version:
    """One USGS version of an event, as the consumer passes it to the model."""

    event_id: str
    updated_at: datetime
    event_time: datetime = field(default_factory=lambda: utc("2026-11-14 10:00"))
    magnitude: float | None = 4.2
    mag_type: str | None = "ml"
    longitude: float = -3.7
    latitude: float = 40.4
    depth_km: float | None = 10.0
    place: str | None = "Madrid, Spain"
    country_id: str | None = "ESP"
    quality_flags: list[str] = field(default_factory=list)
    source: str = "usgs_feed"

    def payload(self) -> dict[str, Any]:
        """A minimal GeoJSON Feature carrying the same values.

        JSON cannot hold NaN or infinity, so those become null here; the typed
        arguments still carry them to the constraint under test.
        """

        def finite(value: float | None) -> float | None:
            return value if value is not None and math.isfinite(value) else None

        return {
            "type": "Feature",
            "id": self.event_id,
            "properties": {
                "mag": finite(self.magnitude),
                "magType": self.mag_type,
                "place": self.place,
                "time": int(self.event_time.timestamp() * 1000),
                "updated": int(self.updated_at.timestamp() * 1000),
                "type": "earthquake",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [finite(self.longitude), finite(self.latitude), finite(self.depth_km)],
            },
        }


@dataclass
class Message:
    """A Kafka message position."""

    topic: str
    partition: int
    offset: int


APPLY_SQL = """
SELECT apply_event_version(
    p_event_id => %s, p_source => %s, p_event_time => %s, p_updated_at => %s,
    p_magnitude => %s, p_mag_type => %s, p_longitude => %s, p_latitude => %s,
    p_depth_km => %s, p_place => %s, p_country_id => %s, p_quality_flags => %s,
    p_payload => %s, p_kafka_topic => %s, p_kafka_partition => %s, p_kafka_offset => %s,
    p_replayed_at => %s
)
"""


def apply_version(
    conn: psycopg.Connection,
    version: Version,
    message: Message | None = None,
    replayed_at: datetime | None = None,
) -> str:
    """Call apply_event_version and return its outcome."""
    message = message or Message("earthquakes.live", 0, 0)
    row = conn.execute(
        APPLY_SQL,
        (
            version.event_id,
            version.source,
            version.event_time,
            version.updated_at,
            version.magnitude,
            version.mag_type,
            version.longitude,
            version.latitude,
            version.depth_km,
            version.place,
            version.country_id,
            version.quality_flags,
            Jsonb(version.payload()),
            message.topic,
            message.partition,
            message.offset,
            replayed_at,
        ),
    ).fetchone()
    assert row is not None
    return row[0]


QUARANTINE_SQL = """
INSERT INTO quarantine (kafka_topic, kafka_partition, kafka_offset, event_id,
                        reason_codes, reason_detail, payload, raw_text, is_synthetic)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING
"""

MESSAGE_LOG_SQL = """
INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, event_id, updated_at, outcome, produced_at)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (kafka_topic, kafka_partition, kafka_offset) DO NOTHING
"""

PUBLISH_STATE_SQL = """
INSERT INTO publish_state (event_id, updated_at)
VALUES (%s, %s)
ON CONFLICT (event_id) DO UPDATE
SET updated_at = EXCLUDED.updated_at, published_at = now()
WHERE EXCLUDED.updated_at > publish_state.updated_at
"""


def quarantine(
    conn: psycopg.Connection,
    message: Message,
    reason_codes: list[str],
    *,
    event_id: str | None = None,
    reason_detail: str = "rejected by the test",
    payload: dict[str, Any] | None = None,
    raw_text: str | None = None,
    is_synthetic: bool = False,
) -> None:
    conn.execute(
        QUARANTINE_SQL,
        (
            message.topic,
            message.partition,
            message.offset,
            event_id,
            reason_codes,
            reason_detail,
            Jsonb(payload) if payload is not None else None,
            raw_text,
            is_synthetic,
        ),
    )


def process_message(
    conn: psycopg.Connection,
    message: Message,
    item: Version | dict[str, Any],
    produced_at: datetime | None = None,
    replayed_at: datetime | None = None,
) -> str:
    """Replay the consumer's per-message transaction (contracts/database.md).

    A Version goes through apply_event_version; a dict describes a rejection
    with keys reason_codes and optionally event_id, payload and raw_text.
    """
    with conn.transaction():
        if isinstance(item, Version):
            outcome = apply_version(conn, item, message, replayed_at)
            event_id, updated_at = item.event_id, item.updated_at
        else:
            quarantine(
                conn,
                message,
                item["reason_codes"],
                event_id=item.get("event_id"),
                payload=item.get("payload"),
                raw_text=item.get("raw_text"),
            )
            outcome, event_id, updated_at = "quarantined", item.get("event_id"), None
        conn.execute(
            MESSAGE_LOG_SQL,
            (message.topic, message.partition, message.offset, event_id, updated_at, outcome, produced_at),
        )
    return outcome


def faq12_sequence() -> list[tuple[Message, Version]]:
    """The example of FAQ 12: E1 10:05 m4.2, repeated, E1 10:09 m4.6, E1 10:05 again, E2 10:12 m3.1."""
    e1_first = Version("E1", utc("2026-11-14 10:05"), magnitude=4.2)
    e1_revised = Version("E1", utc("2026-11-14 10:09"), magnitude=4.6)
    e2 = Version("E2", utc("2026-11-14 10:12"), magnitude=3.1)
    items = [e1_first, e1_first, e1_revised, e1_first, e2]
    return [(Message("earthquakes.live", 0, offset), item) for offset, item in enumerate(items)]


def count(conn: psycopg.Connection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()  # noqa: S608 - fixed table names
    assert row is not None
    return row[0]
