"""USGS producer entrypoint: polls the live feed and publishes new versions."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import asyncpg
from aiokafka import AIOKafkaProducer

from common.db import create_pool
from common.health import Heartbeat
from common.logging import configure
from common.retry import retry
from common.topics import ensure_topics

from .config import ProducerConfig, load_config
from .feed import FeedError, fetch_feed
from .persistence import mark_published, published_versions, should_publish

logger = logging.getLogger(__name__)


def _updated_at(event_id: str, raw: object) -> datetime:
    try:
        return datetime.fromtimestamp(float(raw) / 1000, tz=timezone.utc)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise FeedError(f"Feature {event_id} has invalid updated timestamp") from exc


async def publish_cycle(config: ProducerConfig, producer: AIOKafkaProducer, pool: asyncpg.Pool) -> int:
    topic = config.kafka.topics.live
    feed = await asyncio.to_thread(fetch_feed, config.feed_url)
    logger.info("Fetched %d events from %s", len(feed["features"]), config.feed_url)

    candidates = []
    for feature in feed["features"]:
        if not isinstance(feature, dict):
            raise FeedError("USGS feed contains a non-object feature")
        event_id = feature.get("id")
        if not event_id:
            logger.error("Skipping feature without stable id")
            continue
        properties = feature.get("properties") or {}
        candidates.append((str(event_id), _updated_at(str(event_id), properties.get("updated")), feature))

    published = 0
    async with pool.acquire() as conn:
        known = await published_versions(conn, [event_id for event_id, _, _ in candidates])
        for event_id, updated, feature in candidates:
            if not should_publish(known, event_id, updated):
                continue
            properties = feature.get("properties") or {}
            event = {
                "id": event_id,
                "updated": properties.get("updated"),
                "time": properties.get("time"),
                "mag": properties.get("mag"),
                "place": properties.get("place"),
                "geometry": feature.get("geometry"),
                "properties": properties,
                "source": "USGS",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "mode": "live",
                "original_event": feature,
                "source_topic": topic,
            }
            await producer.send_and_wait(
                topic,
                key=event_id.encode("utf-8"),
                value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
            )
            # Only after Kafka confirmed the message.
            await mark_published(conn, event_id, updated)
            known[event_id] = updated
            published += 1
    logger.info("Published %d earthquake versions to %s", published, topic)
    return published


async def run(config: ProducerConfig) -> None:
    await retry(lambda: ensure_topics(config.kafka), description="creating Kafka topics", log=logger)
    pool = await create_pool(config.database, "core", application_name="producer", max_size=2)
    producer = AIOKafkaProducer(bootstrap_servers=config.kafka.bootstrap_servers, acks="all")
    await retry(producer.start, description="connecting to Kafka", log=logger)
    heartbeat = Heartbeat()
    try:
        while True:
            await retry(lambda: publish_cycle(config, producer, pool), description="producer cycle", log=logger)
            heartbeat.beat()
            await asyncio.sleep(config.interval_seconds)
    finally:
        await producer.stop()
        await pool.close()


def main() -> None:
    configure("producer")
    asyncio.run(run(load_config()))


if __name__ == "__main__":
    main()
