"""Typed reading of the environment variables in contracts/runtime.md.

Nothing is read at import time: each service calls its *from_env* function
at start-up, and a missing or invalid variable raises SettingsError naming it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, urlsplit

Role = Literal["writer", "reader"]

ROLE_USERS: dict[Role, tuple[str, str]] = {
    "writer": ("observatory_writer", "DB_WRITER_PASSWORD"),
    "reader": ("observatory_reader", "DB_READER_PASSWORD"),
}


class SettingsError(RuntimeError):
    """A required environment variable is missing or invalid."""


def required(name: str, env: Mapping[str, str] | None = None) -> str:
    value = (os.environ if env is None else env).get(name, "").strip()
    if not value:
        raise SettingsError(f"Required environment variable {name} is missing or empty")
    return value


def optional(name: str, default: str, env: Mapping[str, str] | None = None) -> str:
    value = (os.environ if env is None else env).get(name, "").strip()
    return value or default


def positive_int(name: str, default: int | None = None, env: Mapping[str, str] | None = None) -> int:
    raw = required(name, env) if default is None else optional(name, str(default), env)
    try:
        value = int(raw)
    except ValueError as exc:
        raise SettingsError(f"Environment variable {name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise SettingsError(f"Environment variable {name} must be greater than zero, got {value}")
    return value


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    database: str
    user: str
    password: str

    def dsn(self) -> str:
        """libpq/asyncpg connection URL; credentials are percent-encoded."""
        return (
            f"postgresql://{quote(self.user, safe='')}:{quote(self.password, safe='')}"
            f"@{self.host}:{self.port}/{quote(self.database, safe='')}"
        )

    def __repr__(self) -> str:  # never print the password
        return f"DatabaseSettings(host={self.host!r}, port={self.port}, database={self.database!r}, user={self.user!r})"


def database(role: Role, env: Mapping[str, str] | None = None) -> DatabaseSettings:
    """Connection settings of one application role."""
    if role not in ROLE_USERS:
        raise SettingsError(f"Unknown database role {role!r}")
    user, password_variable = ROLE_USERS[role]
    return DatabaseSettings(
        host=optional("DB_HOST", "postgres", env),
        port=positive_int("DB_PORT", 5432, env),
        database=required("POSTGRES_DB", env),
        user=user,
        password=required(password_variable, env),
    )


@dataclass(frozen=True)
class TopicNames:
    live: str = "earthquakes.live"
    catalog: str = "earthquakes.catalog"
    replay: str = "earthquakes.replay"

    def all(self) -> tuple[str, str, str]:
        return (self.live, self.catalog, self.replay)


@dataclass(frozen=True)
class KafkaSettings:
    bootstrap_servers: str
    topics: TopicNames
    retention_hours: int


def kafka(env: Mapping[str, str] | None = None) -> KafkaSettings:
    topics = TopicNames(
        live=required("KAFKA_TOPIC_LIVE", env),
        catalog=required("KAFKA_TOPIC_CATALOG", env),
        replay=required("KAFKA_TOPIC_REPLAY", env),
    )
    if len(set(topics.all())) != 3:
        raise SettingsError("KAFKA_TOPIC_LIVE, KAFKA_TOPIC_CATALOG and KAFKA_TOPIC_REPLAY must be different")
    return KafkaSettings(
        bootstrap_servers=required("KAFKA_BOOTSTRAP_SERVERS", env),
        topics=topics,
        retention_hours=positive_int("KAFKA_RETENTION_HOURS", 168, env),
    )


def cors_origins(env: Mapping[str, str] | None = None) -> list[str]:
    """CORS_ORIGINS as a list of exact origins (scheme://host[:port]); no wildcard."""
    raw = required("CORS_ORIGINS", env)
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    if not origins:
        raise SettingsError("CORS_ORIGINS must list at least one origin")
    for origin in origins:
        if "*" in origin:
            raise SettingsError(f"CORS_ORIGINS must list exact origins, wildcard found in {origin!r}")
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/") or parts.query:
            raise SettingsError(f"CORS_ORIGINS entry {origin!r} is not an origin like https://example.org")
    return [origin.rstrip("/") for origin in origins]


DEFAULT_CATALOG_URL = "https://earthquake.usgs.gov/fdsnws/event/1"
DEFAULT_USER_AGENT = "seismic-observatory/1.0"


@dataclass(frozen=True)
class UsgsSettings:
    """How the services talk to USGS (contracts/runtime.md of spec 003)."""

    feed_url: str | None          # required by the producer only
    catalog_url: str              # FDSN event service base, no trailing slash
    timeout_seconds: int
    max_attempts: int             # requests per query, counting the first one
    user_agent: str


def usgs(env: Mapping[str, str] | None = None, *, require_feed: bool = True) -> UsgsSettings:
    return UsgsSettings(
        feed_url=required("USGS_FEED_URL", env) if require_feed else optional("USGS_FEED_URL", "", env) or None,
        catalog_url=optional("USGS_CATALOG_URL", DEFAULT_CATALOG_URL, env).rstrip("/"),
        timeout_seconds=positive_int("USGS_TIMEOUT_SECONDS", 30, env),
        max_attempts=positive_int("USGS_MAX_ATTEMPTS", 4, env),
        user_agent=optional("USGS_USER_AGENT", DEFAULT_USER_AGENT, env),
    )


@dataclass(frozen=True)
class ProducerSettings:
    database: DatabaseSettings
    kafka: KafkaSettings
    feed_url: str
    interval_seconds: int
    raw_payload_retention_days: int
    usgs: UsgsSettings
    gap_margin_minutes: int


def producer(env: Mapping[str, str] | None = None) -> ProducerSettings:
    source = usgs(env, require_feed=True)
    assert source.feed_url is not None
    return ProducerSettings(
        database=database("writer", env),
        kafka=kafka(env),
        feed_url=source.feed_url,
        interval_seconds=positive_int("PRODUCER_INTERVAL_SECONDS", 60, env),
        raw_payload_retention_days=positive_int("RAW_PAYLOAD_RETENTION_DAYS", 7, env),
        usgs=source,
        gap_margin_minutes=positive_int("GAP_MARGIN_MINUTES", 60, env),
    )


@dataclass(frozen=True)
class CatalogLoaderSettings:
    database: DatabaseSettings
    kafka: KafkaSettings
    usgs: UsgsSettings
    gap_margin_minutes: int
    data_dir: str


def catalog_loader(env: Mapping[str, str] | None = None) -> CatalogLoaderSettings:
    """Settings of the manual catalog load; it never needs the live feed URL."""
    return CatalogLoaderSettings(
        database=database("writer", env),
        kafka=kafka(env),
        usgs=usgs(env, require_feed=False),
        gap_margin_minutes=positive_int("GAP_MARGIN_MINUTES", 60, env),
        data_dir=optional("DATA_DIR", "/data", env),
    )


@dataclass(frozen=True)
class ReplaySettings:
    database: DatabaseSettings
    kafka: KafkaSettings
    data_dir: str
    default_rate: float


def replay(env: Mapping[str, str] | None = None) -> ReplaySettings:
    """Settings of the replay command; it needs neither the feed URL nor USGS."""
    raw = optional("REPLAY_DEFAULT_RATE", "50", env)
    try:
        rate = float(raw)
    except ValueError as exc:
        raise SettingsError(f"Environment variable REPLAY_DEFAULT_RATE must be a number, got {raw!r}") from exc
    if not rate > 0 or rate == float("inf"):
        raise SettingsError(f"Environment variable REPLAY_DEFAULT_RATE must be greater than zero, got {raw!r}")
    return ReplaySettings(
        database=database("writer", env),
        kafka=kafka(env),
        data_dir=optional("DATA_DIR", "/data", env),
        default_rate=rate,
    )


@dataclass(frozen=True)
class ConsumerSettings:
    database: DatabaseSettings
    kafka: KafkaSettings
    group_id: str
    countries_path: str


def consumer(env: Mapping[str, str] | None = None) -> ConsumerSettings:
    return ConsumerSettings(
        database=database("writer", env),
        kafka=kafka(env),
        group_id=required("KAFKA_GROUP_ID", env),
        countries_path=required("COUNTRIES_GEOJSON_PATH", env),
    )


@dataclass(frozen=True)
class ApiSettings:
    database: DatabaseSettings
    cors_origins: list[str]
    api_prefix: str


def api(env: Mapping[str, str] | None = None) -> ApiSettings:
    prefix = "/" + optional("API_PREFIX", "/api", env).strip("/")
    return ApiSettings(database=database("reader", env), cors_origins=cors_origins(env), api_prefix=prefix)
