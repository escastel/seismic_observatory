"""Configuration for the streaming consumer."""

from dataclasses import dataclass
import os


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class ConsumerConfig:
    kafka_bootstrap_servers: str = _required_env("KAFKA_BOOTSTRAP_SERVERS")
    kafka_group_id: str = _required_env("KAFKA_GROUP_ID")
    raw_topic: str = _required_env("KAFKA_RAW_TOPIC")
    replay_topic: str = _required_env("KAFKA_REPLAY_TOPIC")
    database_dsn: str = _required_env("DATABASE_DSN")
    countries_path: str = _required_env("COUNTRIES_GEOJSON_PATH")
