"""Accelerated publisher for the reproducible 2025 historical batch."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaProducer

from .config import ProducerConfig

logger = logging.getLogger(__name__)


def _event_year(event: dict[str, Any]) -> int | None:
    value = event.get("time")
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).year
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def read_replay_events(path: str | Path, topic: str) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Replay file does not exist: {source}")

    events: list[dict[str, Any]] = []
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {source}:{line_number}: {exc}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"Replay event at {source}:{line_number} is not an object")
            if _event_year(event) != 2025:
                raise ValueError(f"Replay event at {source}:{line_number} is not from 2025")
            event["source_topic"] = topic
            events.append(event)
    if not events:
        raise ValueError(f"Replay file is empty: {source}")
    return events


async def publish_replay(
    config: ProducerConfig,
    path: str | Path,
    rate: float,
) -> int:
    if rate <= 0:
        raise ValueError("Replay rate must be greater than zero")
    events = read_replay_events(path, config.replay_topic)
    producer = AIOKafkaProducer(bootstrap_servers=config.kafka_bootstrap_servers)
    published = 0
    delay = 1 / rate
    await producer.start()
    try:
        for event in events:
            event_id = event.get("id")
            if not isinstance(event_id, str) or not event_id:
                raise ValueError("Replay event id must be a non-empty string")
            await producer.send_and_wait(
                config.replay_topic,
                key=event_id.encode("utf-8"),
                value=json.dumps(event, separators=(",", ":")).encode("utf-8"),
            )
            published += 1
            await asyncio.sleep(delay)
    finally:
        await producer.stop()
    logger.info(
        "Replay complete source=%s topic=%s published=%d rate=%.2f events/sec",
        path,
        config.replay_topic,
        published,
        rate,
    )
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the 2025 seismic history to Kafka")
    parser.add_argument(
        "--path",
        default="/data/seeds/historical_2025.jsonl",
        help="JSONL replay file path",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=10.0,
        help="Target events per second (default: 10)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(publish_replay(ProducerConfig(), args.path, args.rate))


if __name__ == "__main__":
    main()
