"""Accelerated publisher for the reproducible 2025 historical batch."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiokafka import AIOKafkaProducer

if TYPE_CHECKING:
    from .config import ProducerConfig

logger = logging.getLogger(__name__)


def _resolve_replay_path(path: str | Path) -> Path:
    source = Path(path)
    if source.is_file():
        return source
    mounted_source = Path("/data/seeds") / source.name
    if mounted_source.is_file():
        logger.warning("Replay path %s mapped to mounted path %s", source, mounted_source)
        return mounted_source
    raise FileNotFoundError(
        f"Replay file does not exist: {source}. "
        f"Inside Docker use /data/seeds/{source.name}"
    )


def _event_year(event: dict[str, Any]) -> int | None:
    properties = event.get("properties")
    value = event.get("time")
    if value is None and isinstance(properties, dict):
        value = properties.get("time")
    try:
        timestamp = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=float(value))
        return timestamp.year
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def read_replay_events(
    path: str | Path,
    topic: str,
    expected_year: int | None = None,
) -> list[dict[str, Any]]:
    source = _resolve_replay_path(path)

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
            event_year = _event_year(event)
            if event_year is None:
                raise ValueError(f"Replay event at {source}:{line_number} has no valid year")
            if expected_year is not None and event_year != expected_year:
                raise ValueError(
                    f"Replay event at {source}:{line_number} is not from {expected_year}"
                )
            event["source_topic"] = topic
            events.append(event)
    if not events:
        raise ValueError(f"Replay file is empty: {source}")
    return events


async def publish_replay(
    config: ProducerConfig,
    path: str | Path,
    rate: float,
    expected_year: int | None = None,
) -> int:
    if rate <= 0:
        raise ValueError("Replay rate must be greater than zero")
    from .config import ProducerConfig

    if not isinstance(config, ProducerConfig):
        raise TypeError("config must be a ProducerConfig")
    events = read_replay_events(path, config.replay_topic, expected_year)
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
    from .config import ProducerConfig

    parser = argparse.ArgumentParser(description="Publish a historical seismic batch to Kafka")
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
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Require every event to belong to this year; omit to infer from the file",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(publish_replay(ProducerConfig(), args.path, args.rate, args.year))


if __name__ == "__main__":
    main()
