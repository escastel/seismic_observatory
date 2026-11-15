"""Environment contract of common.settings (contracts/runtime.md)."""

from __future__ import annotations

import pytest

from common import settings
from common.settings import SettingsError

BASE = {
    "POSTGRES_DB": "observatory",
    "DB_WRITER_PASSWORD": "w-secret",
    "DB_READER_PASSWORD": "r-secret",
    "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092",
    "KAFKA_TOPIC_LIVE": "earthquakes.live",
    "KAFKA_TOPIC_CATALOG": "earthquakes.catalog",
    "KAFKA_TOPIC_REPLAY": "earthquakes.replay",
    "KAFKA_GROUP_ID": "observatory-consumer",
    "USGS_FEED_URL": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
    "COUNTRIES_GEOJSON_PATH": "/catalog/paises.geojson",
    "CORS_ORIGINS": "https://observatorio.netlify.app,http://localhost:4200",
}


@pytest.mark.parametrize(
    ("loader", "variable"),
    [
        (settings.producer, "USGS_FEED_URL"),
        (settings.producer, "DB_WRITER_PASSWORD"),
        (settings.consumer, "KAFKA_GROUP_ID"),
        (settings.consumer, "COUNTRIES_GEOJSON_PATH"),
        (settings.api, "DB_READER_PASSWORD"),
        (settings.api, "CORS_ORIGINS"),
        (settings.api, "POSTGRES_DB"),
    ],
)
def test_missing_required_variable_is_named(loader, variable: str) -> None:
    env = {key: value for key, value in BASE.items() if key != variable}
    with pytest.raises(SettingsError, match=variable):
        loader(env)


def test_empty_value_counts_as_missing() -> None:
    with pytest.raises(SettingsError, match="KAFKA_BOOTSTRAP_SERVERS"):
        settings.consumer({**BASE, "KAFKA_BOOTSTRAP_SERVERS": "  "})


@pytest.mark.parametrize("value", ["*", "https://*.netlify.app", "http://localhost:4200,*"])
def test_cors_wildcard_is_rejected(value: str) -> None:
    with pytest.raises(SettingsError, match="CORS_ORIGINS"):
        settings.api({**BASE, "CORS_ORIGINS": value})


@pytest.mark.parametrize("value", ["observatorio.netlify.app", "https://site.netlify.app/api", "ftp://host"])
def test_cors_entries_must_be_origins(value: str) -> None:
    with pytest.raises(SettingsError, match="CORS_ORIGINS"):
        settings.api({**BASE, "CORS_ORIGINS": value})


def test_cors_origins_are_an_exact_list() -> None:
    assert settings.api(BASE).cors_origins == ["https://observatorio.netlify.app", "http://localhost:4200"]


def test_each_role_gets_its_own_user_and_password() -> None:
    writer = settings.producer(BASE).database
    reader = settings.api(BASE).database
    assert (writer.user, writer.password) == ("observatory_writer", "w-secret")
    assert (reader.user, reader.password) == ("observatory_reader", "r-secret")
    assert reader.dsn() == "postgresql://observatory_reader:r-secret@postgres:5432/observatory"


def test_dsn_escapes_special_characters() -> None:
    writer = settings.producer({**BASE, "DB_WRITER_PASSWORD": "p@ss:w/rd"}).database
    assert writer.dsn() == "postgresql://observatory_writer:p%40ss%3Aw%2Frd@postgres:5432/observatory"


def test_password_never_appears_in_repr() -> None:
    assert "w-secret" not in repr(settings.producer(BASE))


def test_defaults_of_optional_variables() -> None:
    producer = settings.producer(BASE)
    assert producer.interval_seconds == 60
    assert producer.raw_payload_retention_days == 7
    assert producer.kafka.retention_hours == 168
    assert (producer.database.host, producer.database.port) == ("postgres", 5432)


def test_numeric_variables_are_validated() -> None:
    with pytest.raises(SettingsError, match="PRODUCER_INTERVAL_SECONDS"):
        settings.producer({**BASE, "PRODUCER_INTERVAL_SECONDS": "soon"})
    with pytest.raises(SettingsError, match="KAFKA_RETENTION_HOURS"):
        settings.producer({**BASE, "KAFKA_RETENTION_HOURS": "0"})


def test_topics_must_be_different() -> None:
    with pytest.raises(SettingsError, match="different"):
        settings.consumer({**BASE, "KAFKA_TOPIC_REPLAY": "earthquakes.live"})


def test_usgs_defaults() -> None:
    source = settings.producer(BASE).usgs
    assert source.feed_url == BASE["USGS_FEED_URL"]
    assert source.catalog_url == "https://earthquake.usgs.gov/fdsnws/event/1"
    assert (source.timeout_seconds, source.max_attempts) == (30, 4)
    assert source.user_agent == "seismic-observatory/1.0"
    assert settings.producer(BASE).gap_margin_minutes == 60


def test_catalog_url_loses_its_trailing_slash() -> None:
    env = {**BASE, "USGS_CATALOG_URL": "http://usgs-stub:8080/fdsnws/event/1/"}
    assert settings.producer(env).usgs.catalog_url == "http://usgs-stub:8080/fdsnws/event/1"


@pytest.mark.parametrize("variable", ["USGS_TIMEOUT_SECONDS", "USGS_MAX_ATTEMPTS", "GAP_MARGIN_MINUTES"])
@pytest.mark.parametrize("value", ["0", "-3", "soon"])
def test_usgs_numbers_must_be_positive_integers(variable: str, value: str) -> None:
    with pytest.raises(SettingsError, match=variable):
        settings.producer({**BASE, variable: value})


def test_catalog_loader_does_not_need_the_feed_url() -> None:
    env = {key: value for key, value in BASE.items() if key != "USGS_FEED_URL"}
    loader = settings.catalog_loader(env)
    assert loader.usgs.feed_url is None
    assert loader.data_dir == "/data"
    assert loader.database.user == "observatory_writer"
    assert loader.gap_margin_minutes == 60
