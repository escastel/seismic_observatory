"""Kafka consumer: one database transaction per message, offset committed after it.

Offset guarantees (principle II, research.md R20):
- automatic commit is disabled and a group without committed offsets starts
  at the beginning of each topic;
- the offset of a message is committed only after its transaction commits;
- if processing fails, the same message is retried with backoff and no later
  offset is committed meanwhile. A quarantined message counts as processed.
- a version the data model refuses (constraint or data error) is not retried
  forever: it goes to quarantine, so one bad record never blocks the topic.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Protocol

import asyncpg
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition

from common import settings as common_settings
from common.db import create_pool
from common.health import Heartbeat
from common.logging import configure
from common.retry import retry
from common.settings import ConsumerSettings, TopicNames
from common.topics import ensure_topics, search_path_for

from .persistence import Position, log_message, store_exclusion, store_rejection, store_version
from .rules import Accepted, Exclusion, Quarantine, evaluate
from .spatial import SpatialEnricher

logger = logging.getLogger(__name__)

POLL_TIMEOUT_MS = 5_000
MAX_RECORDS = 100

# Errors that will repeat on every retry of the same message: the data model
# rejects the values. Anything else (connection lost, server restarting) is
# transient and the same message is retried.
PERMANENT_DATABASE_ERRORS: tuple[type[BaseException], ...] = (
    asyncpg.IntegrityConstraintViolationError,
    asyncpg.DataError,
)


class KafkaMessage(Protocol):
    topic: str
    partition: int
    offset: int
    value: bytes


class Consumer(Protocol):
    async def getmany(self, *partitions: TopicPartition, timeout_ms: int = 0, max_records: int | None = None) -> dict: ...
    async def commit(self, offsets: Mapping[TopicPartition, int] | None = None) -> None: ...


def consumer_options(config: ConsumerSettings) -> dict[str, Any]:
    """Keyword arguments of AIOKafkaConsumer that carry the offset guarantees."""
    return {
        "bootstrap_servers": config.kafka.bootstrap_servers,
        "group_id": config.group_id,
        "enable_auto_commit": False,
        "auto_offset_reset": "earliest",
    }


def source_for(topic: str, topics: TopicNames) -> str:
    """USGS origin of the versions carried by a topic."""
    return "usgs_feed" if topic == topics.live else "usgs_catalog"


async def consume(
    consumer: Consumer,
    handle: Callable[[KafkaMessage], Awaitable[str]],
    *,
    heartbeat: Heartbeat | None = None,
    stop: asyncio.Event | None = None,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> None:
    """Poll, process each message until it succeeds, then commit its offset."""
    while stop is None or not stop.is_set():
        batches = await consumer.getmany(timeout_ms=POLL_TIMEOUT_MS, max_records=MAX_RECORDS)
        for partition, messages in batches.items():
            for message in messages:
                outcome = await retry(
                    lambda message=message: handle(message),
                    description=f"processing {message.topic}[{message.partition}]@{message.offset}",
                    sleep=sleep,
                    log=logger,
                )
                await retry(
                    lambda partition=partition, message=message: consumer.commit({partition: message.offset + 1}),
                    description=f"committing offset {message.offset + 1} of {message.topic}[{message.partition}]",
                    sleep=sleep,
                    log=logger,
                )
                logger.info(
                    "Processed topic=%s partition=%d offset=%d outcome=%s",
                    message.topic, message.partition, message.offset, outcome,
                )
        if heartbeat is not None:
            heartbeat.beat()


def _decoded(value: bytes) -> dict[str, Any]:
    """The message as an object, or {} when it is not one (the rules already judged it)."""
    try:
        decoded = json.loads(value, parse_constant=lambda name: None)
    except (UnicodeDecodeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _extraction_id(decoded: dict[str, Any]) -> int | None:
    value = decoded.get("extraction_id")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _produced_at(decoded: dict[str, Any]) -> datetime | None:
    value = decoded.get("ingested_at")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


SYNTHETIC_KEY_PREFIX = b"synthetic-"


def _mark_synthetic_key(result: Any, message: Any) -> Any:
    """A message keyed ``synthetic-...`` is synthetic even if its body cannot be read.

    The Kafka key is the event id (contracts/messages.md), so the reserved prefix identifies the
    damaged-on-purpose messages whose JSON is unreadable and cannot carry the marker themselves.
    """
    key = getattr(message, "key", None) or b""
    if not key.startswith(SYNTHETIC_KEY_PREFIX) or result.synthetic:
        return result
    if isinstance(result, Accepted):
        return replace(result, synthetic=True, flags=sorted({*result.flags, "synthetic"}))
    return replace(result, synthetic=True)


class MessageHandler:
    """Validates one message and writes it with the search_path of its topic."""

    def __init__(self, pools: Mapping[str, asyncpg.Pool], topics: TopicNames, spatial: SpatialEnricher) -> None:
        self.pools = pools
        self.topics = topics
        self.spatial = spatial

    async def __call__(self, message: KafkaMessage) -> str:
        search_path = search_path_for(message.topic, self.topics)
        position = Position(message.topic, message.partition, message.offset)
        result = _mark_synthetic_key(evaluate(message.value, datetime.now(timezone.utc)), message)
        decoded = _decoded(message.value)
        produced_at = _produced_at(decoded)
        if isinstance(result, Quarantine):
            return await self._write(search_path, position, result, produced_at=produced_at)
        if isinstance(result, Exclusion):
            return await self._write(
                search_path, position, result, produced_at=produced_at, extraction_id=_extraction_id(decoded)
            )

        country_id, ambiguous = self.spatial.lookup(result.event.longitude, result.event.latitude)
        if ambiguous:
            result = replace(result, flags=sorted({*result.flags, "ambiguous_country"}))
        try:
            return await self._write(search_path, position, result, country_id=country_id, produced_at=produced_at)
        except PERMANENT_DATABASE_ERRORS as exc:
            # The model refused a version the rules accepted (for example a date
            # outside dim_date). Retrying would block the topic forever
            # (principle III), so the message goes to quarantine with the reason.
            logger.warning(
                "Model rejected topic=%s partition=%d offset=%d event_id=%s: %s",
                message.topic, message.partition, message.offset, result.event.external_id, exc,
            )
            rejection = Quarantine(
                reasons=["model_constraint_violation"],
                detail=f"Consistencia: model_constraint_violation ({type(exc).__name__}: {exc})",
                payload=decoded,
                raw_text=None,
                event_id=result.event.external_id,
                synthetic=result.synthetic,
            )
            return await self._write(search_path, position, rejection, produced_at=produced_at)

    async def _write(
        self,
        search_path: str,
        position: Position,
        result: Accepted | Exclusion | Quarantine,
        *,
        country_id: str | None = None,
        produced_at: datetime | None = None,
        extraction_id: int | None = None,
    ) -> str:
        replayed_at = datetime.now(timezone.utc) if position.topic == self.topics.replay else None
        updated_at: datetime | None = None
        async with self.pools[search_path].acquire() as conn:
            async with conn.transaction():
                if isinstance(result, Quarantine):
                    outcome = await store_rejection(conn, position, result)
                    event_id = result.event_id
                elif isinstance(result, Exclusion):
                    outcome = await store_exclusion(conn, result, extraction_id)
                    event_id, updated_at = result.event_id, result.updated_at
                else:
                    outcome = await store_version(
                        conn,
                        position,
                        result.event,
                        source=source_for(position.topic, self.topics),
                        country_id=country_id,
                        flags=result.flags,
                        original=result.original,
                        replayed_at=replayed_at,
                    )
                    event_id, updated_at = result.event.external_id, result.event.updated
                await log_message(
                    conn, position, outcome=outcome, event_id=event_id, updated_at=updated_at, produced_at=produced_at
                )
        return outcome


async def run(config: ConsumerSettings) -> None:
    from .spatial import CatalogError

    spatial = SpatialEnricher(config.countries_path)
    await retry(lambda: ensure_topics(config.kafka), description="creating Kafka topics", log=logger)
    pools = {
        "core": await create_pool(config.database, "core", application_name="consumer"),
        "replay, core": await create_pool(config.database, "replay, core", application_name="consumer-replay"),
    }
    try:
        async with pools["core"].acquire() as conn:
            known = {row["country_id"] for row in await conn.fetch("SELECT country_id FROM dim_country")}
        spatial.verify_against_dimension(known)
    except CatalogError as exc:
        logger.error("Country catalog does not match core.dim_country: %s", exc)
        for pool in pools.values():
            await pool.close()
        raise SystemExit(1) from exc
    consumer = AIOKafkaConsumer(*config.kafka.topics.all(), **consumer_options(config))
    await retry(consumer.start, description="connecting to Kafka", log=logger)
    heartbeat = Heartbeat()
    heartbeat.beat()
    logger.info("Consuming %s as group %s", ", ".join(config.kafka.topics.all()), config.group_id)
    try:
        await consume(consumer, MessageHandler(pools, config.kafka.topics, spatial), heartbeat=heartbeat)
    finally:
        await consumer.stop()
        for pool in pools.values():
            await pool.close()


def main() -> None:
    configure("consumer")
    asyncio.run(run(common_settings.consumer()))


if __name__ == "__main__":
    main()
