"""Kafka topics of the observatory and the schema each one writes to."""

from __future__ import annotations

import logging

from aiokafka.admin import AIOKafkaAdminClient, NewTopic

from .settings import KafkaSettings, TopicNames

logger = logging.getLogger(__name__)

TOPIC_ALREADY_EXISTS = 36  # Kafka protocol error code
PARTITIONS = 1
REPLICATION_FACTOR = 1


class UnknownTopicError(ValueError):
    """A message came from a topic that has no destination schema."""


def search_path_for(topic: str, topics: TopicNames) -> str:
    """search_path for messages of a topic: core for real data, replay first for replays.

    An unknown topic is an error, never a default destination: a misrouted
    message must not end up in core.
    """
    if topic in (topics.live, topics.catalog):
        return "core"
    if topic == topics.replay:
        return "replay, core"
    raise UnknownTopicError(f"Topic {topic!r} has no destination schema")


def retention_ms(hours: int) -> int:
    return hours * 3_600_000


async def ensure_topics(settings: KafkaSettings) -> list[str]:
    """Create the missing topics (1 partition, explicit retention). Returns the ones created.

    Idempotent: producer and consumer both call it at start-up, and the broker
    has automatic topic creation disabled.
    """
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.bootstrap_servers)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        missing = [name for name in settings.topics.all() if name not in existing]
        if not missing:
            return []
        config = {"retention.ms": str(retention_ms(settings.retention_hours))}
        response = await admin.create_topics(
            [NewTopic(name, PARTITIONS, REPLICATION_FACTOR, topic_configs=config) for name in missing]
        )
        for error in response.topic_errors:
            name, code = error[0], error[1]
            if code not in (0, TOPIC_ALREADY_EXISTS):
                message = error[2] if len(error) > 2 else ""
                raise RuntimeError(f"Kafka refused to create topic {name}: error {code} {message}")
        logger.info("Created Kafka topics %s with retention %d h", ", ".join(missing), settings.retention_hours)
        return missing
    finally:
        await admin.close()
