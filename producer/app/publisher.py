"""Publication of earthquake versions to Kafka, shared by the feed and the catalog load.

Rules (FAQ 10, enunciado §5.3–§5.5, research R6, contracts/messages.md):
- publish a version only if its updated is later than the one recorded in
  core.publish_state for that event (unknown events are published);
- key = event_id; the message carries source, ingested_at, mode and the
  original feature;
- mark the version as published only after Kafka confirmed it. If sending
  fails, publication stops there: what was confirmed stays marked, the rest is
  left for the next attempt, and the error is returned to the caller.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import asyncpg

from .classify import Item
from .persistence import mark_published, published_versions, should_publish

MODE_LIVE = "live"


class KafkaProducer(Protocol):
    async def send_and_wait(self, topic: str, value: bytes | None = None, key: bytes | None = None, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class PublishOutcome:
    published: int                     # versions confirmed by Kafka and marked
    pending: list[Item]                # versions that should have been published but were not
    error: BaseException | None = None


def build_message(feature: dict[str, Any], *, source: str, extraction_id: int, ingested_at: datetime) -> dict[str, Any]:
    """Message value of contracts/messages.md; the consumer reads the top-level copies."""
    properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    return {
        "id": feature.get("id"),
        "updated": properties.get("updated"),
        "time": properties.get("time"),
        "mag": properties.get("mag"),
        "place": properties.get("place"),
        "geometry": feature.get("geometry"),
        "properties": properties,
        "source": source,
        "ingested_at": ingested_at.astimezone(timezone.utc).isoformat(),
        "mode": MODE_LIVE,
        "extraction_id": extraction_id,
        "original_event": feature,
    }


def encode(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def latest_per_event(items: Sequence[Item]) -> list[Item]:
    """One item per event: its latest version (a catalog interval may repeat an event)."""
    latest: dict[str, Item] = {}
    for item in items:
        current = latest.get(item.event_id)
        if current is None or item.updated_at > current.updated_at:
            latest[item.event_id] = item
    return sorted(latest.values(), key=lambda item: (item.updated_at, item.event_id))


async def publish_versions(
    producer: KafkaProducer,
    conn: asyncpg.Connection,
    topic: str,
    earthquakes: Sequence[Item],
    *,
    source: str,
    extraction_id: int,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> PublishOutcome:
    """Publish the versions not yet published; stop at the first Kafka failure."""
    candidates = latest_per_event(earthquakes)
    known = await published_versions(conn, [item.event_id for item in candidates])
    to_publish = [item for item in candidates if should_publish(known, item.event_id, item.updated_at)]

    published = 0
    for index, item in enumerate(to_publish):
        message = build_message(item.feature, source=source, extraction_id=extraction_id, ingested_at=now())
        try:
            await producer.send_and_wait(topic, value=encode(message), key=item.event_id.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - any send failure leaves the rest pending
            return PublishOutcome(published, to_publish[index:], exc)
        await mark_published(conn, item.event_id, item.updated_at)
        published += 1
    return PublishOutcome(published, [])
