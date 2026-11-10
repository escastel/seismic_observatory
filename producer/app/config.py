"""Configuration for the seismic event producer."""

from dataclasses import dataclass
import os


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class ProducerConfig:
    kafka_bootstrap_servers: str = _required_env("KAFKA_BOOTSTRAP_SERVERS")
    raw_topic: str = _required_env("KAFKA_RAW_TOPIC")
    replay_topic: str = _required_env("KAFKA_REPLAY_TOPIC")
    feed_url: str = _required_env("USGS_FEED_URL")
    interval_seconds: int = int(_required_env("PRODUCER_INTERVAL_SECONDS"))
