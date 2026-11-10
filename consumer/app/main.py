"""Kafka consumer and transactional ETL pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition

from .config import ConsumerConfig
from .persistence import persist_event, persist_quarantine, persist_quarantines
from .quality import validate_event
from .spatial import SpatialEnricher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def _quarantine_payload(raw: bytes) -> Any:
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw_payload": raw.decode("utf-8", errors="replace")}


async def process_message(
    message: Any,
    config: ConsumerConfig,
    spatial: SpatialEnricher,
) -> bool:
    source_topic = message.topic
    payload = _quarantine_payload(message.value)
    try:
        decoded = json.loads(message.value)
    except (UnicodeDecodeError, json.JSONDecodeError):
        persist_quarantine(
            config.database_dsn, payload, None, source_topic, message.partition, message.offset,
            "Validez", "malformed_json", "Kafka message is not valid JSON",
        )
        return True

    event, failures = validate_event(decoded)
    if failures:
        external_id = decoded.get("id") if isinstance(decoded, dict) else None
        persist_quarantines(
            config.database_dsn,
            [
                (
                    payload,
                    external_id,
                    source_topic,
                    message.partition,
                    message.offset,
                    failure.dimension,
                    failure.reason_code,
                    failure.reason_detail,
                )
                for failure in failures
            ],
        )
        return True

    geography = spatial.lookup(event.longitude, event.latitude)
    persist_event(config.database_dsn, event, geography, source_topic)
    logger.info(
        "Persisted event source_topic=%s kafka_partition=%s kafka_offset=%s external_id=%s updated=%s",
        source_topic, message.partition, message.offset, event.external_id, event.updated.isoformat(),
    )
    return False


async def run(config: ConsumerConfig) -> None:
    consumer = AIOKafkaConsumer(
        config.raw_topic,
        config.replay_topic,
        bootstrap_servers=config.kafka_bootstrap_servers,
        group_id=config.kafka_group_id,
        enable_auto_commit=False,
        value_deserializer=None,
    )
    spatial = SpatialEnricher(config.countries_path)
    processed = 0
    quarantined = 0
    failures = 0
    await consumer.start()
    try:
        async for message in consumer:
            try:
                was_quarantined = await process_message(message, config, spatial)
                await consumer.commit()
                processed += 1
                topic_partition = TopicPartition(message.topic, message.partition)
                position = await consumer.position(topic_partition)
                highwater = consumer.highwater(topic_partition)
                lag = max(0, highwater - position) if highwater is not None else -1
                quarantined += int(was_quarantined)
                logger.info(
                    "Consumer metrics processed=%d quarantined=%d failures=%d lag=%d "
                    "source_topic=%s kafka_partition=%s kafka_offset=%s",
                    processed, quarantined, failures, lag,
                    message.topic, message.partition, message.offset,
                )
            except Exception:
                failures += 1
                logger.exception(
                    "Message processing failed; offset remains uncommitted "
                    "source_topic=%s kafka_partition=%s kafka_offset=%s",
                    message.topic, message.partition, message.offset,
                )
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(run(ConsumerConfig()))


if __name__ == "__main__":
    main()
