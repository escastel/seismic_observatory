"""USGS producer entrypoint."""

from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer

from .config import ProducerConfig
from .feed import FeedError, fetch_feed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def publish_cycle(config: ProducerConfig, producer: AIOKafkaProducer) -> int:
    feed = fetch_feed(config.feed_url)
    published = 0
    for feature in feed["features"]:
        if not isinstance(feature, dict):
            raise FeedError("USGS feed contains a non-object feature")
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry")
        event_id = feature.get("id")
        if not event_id:
            logger.error("Skipping feature without stable id")
            continue
        event = {
            "id": event_id,
            "updated": properties.get("updated"),
            "time": properties.get("time"),
            "mag": properties.get("mag"),
            "place": properties.get("place"),
            "geometry": geometry,
            "properties": properties,
            "source_topic": config.raw_topic,
        }
        await producer.send_and_wait(
            config.raw_topic,
            key=str(event_id).encode("utf-8"),
            value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
        )
        published += 1
    logger.info("Published %d earthquake features to %s", published, config.raw_topic)
    return published


async def run(config: ProducerConfig) -> None:
    producer = AIOKafkaProducer(bootstrap_servers=config.kafka_bootstrap_servers)
    while True:
        try:
            await producer.start()
            await publish_cycle(config, producer)
            await producer.stop()
            await asyncio.sleep(config.interval_seconds)
        except (FeedError, OSError, RuntimeError) as exc:
            logger.exception("Producer cycle failed; retrying: %s", exc)
            try:
                await producer.stop()
            except RuntimeError:
                logger.exception("Producer shutdown failed")
            await asyncio.sleep(min(config.interval_seconds, 30))


def main() -> None:
    asyncio.run(run(ProducerConfig()))


if __name__ == "__main__":
    main()
