"""USGS producer entrypoint."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
import psycopg2

from .config import ProducerConfig
from .feed import FeedError, fetch_feed
from .persistence import ensure_state_table, mark_published, should_publish

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def publish_cycle(config: ProducerConfig, producer: AIOKafkaProducer) -> int:
    feed = fetch_feed(config.feed_url)
    logger.info("Fetched %d events from %s", len(feed["features"]), config.feed_url)
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
        updated_raw = properties.get("updated")
        try:
            updated = datetime.fromtimestamp(float(updated_raw) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError) as exc:
            raise FeedError(f"Feature {event_id} has invalid updated timestamp") from exc
        if not should_publish(config.database_dsn, str(event_id), updated):
            logger.info("Skipping already published version external_id=%s", event_id)
            continue
        event = {
            "id": event_id,
            "updated": updated_raw,
            "time": properties.get("time"),
            "mag": properties.get("mag"),
            "place": properties.get("place"),
            "geometry": geometry,
            "properties": properties,
            "source": "USGS",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "mode": "live",
            "original_event": feature,
            "source_topic": config.raw_topic,
        }
        await producer.send_and_wait(
            config.raw_topic,
            key=str(event_id).encode("utf-8"),
            value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
        )
        mark_published(config.database_dsn, str(event_id), updated)
        published += 1
    logger.info("Published %d earthquake features to %s", published, config.raw_topic)
    return published


async def run(config: ProducerConfig) -> None:
    while True:
        try:
            ensure_state_table(config.database_dsn)
            break
        except (OSError, psycopg2.Error):
            logger.exception("Producer state database unavailable; retrying in 10 seconds")
            await asyncio.sleep(10)
    retries = 0
    while True:
        producer: AIOKafkaProducer | None = None
        cycle_succeeded = False
        try:
            producer = AIOKafkaProducer(bootstrap_servers=config.kafka_bootstrap_servers)
            await producer.start()
            await publish_cycle(config, producer)
            cycle_succeeded = True
        except KafkaError as exc:
            retries += 1
            logger.exception("Kafka failure in producer cycle; retrying: %s", exc)
            logger.info("Producer metrics retries=%d", retries)
        except (FeedError, OSError, RuntimeError) as exc:
            retries += 1
            logger.exception("Producer cycle failed; retrying: %s", exc)
            logger.info("Producer metrics retries=%d", retries)
        except Exception as exc:
            retries += 1
            logger.exception("Unexpected producer failure; retrying: %s", exc)
            logger.info("Producer metrics retries=%d", retries)
        finally:
            if producer is not None:
                try:
                    await producer.stop()
                except Exception:
                    logger.exception("Producer shutdown failed")

        await asyncio.sleep(config.interval_seconds if cycle_succeeded else 10)


def main() -> None:
    asyncio.run(run(ProducerConfig()))


if __name__ == "__main__":
    main()
