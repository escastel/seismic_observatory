"""The consumer's per-message transaction against the real model (contracts/database.md).

Drives consumer.app.main.MessageHandler with asyncpg pools on the test
database, as observatory_writer, exactly as the service does.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.db import open_pool  # noqa: E402
from common.settings import DatabaseSettings, TopicNames  # noqa: E402
from consumer.app.main import MessageHandler  # noqa: E402

TOPICS = TopicNames()


@dataclass
class FakeMessage:
    topic: str
    offset: int
    value: bytes
    partition: int = 0


class FixedCountry:
    def __init__(self, country_id: str | None) -> None:
        self.country_id = country_id

    def lookup(self, longitude: float, latitude: float) -> str | None:
        return self.country_id


def feature_message(event_id: str, event_time: datetime, updated: datetime, mag: float | None = 4.2) -> bytes:
    def ms(moment: datetime) -> int:
        return int(moment.timestamp() * 1000)

    feature = {
        "type": "Feature",
        "id": event_id,
        "properties": {"mag": mag, "magType": "ml", "place": "Test", "time": ms(event_time), "updated": ms(updated), "type": "earthquake"},
        "geometry": {"type": "Point", "coordinates": [-3.7, 40.4, 10.0]},
    }
    message = {
        "id": event_id,
        "updated": ms(updated),
        "time": ms(event_time),
        "mag": mag,
        "place": "Test",
        "geometry": feature["geometry"],
        "properties": feature["properties"],
        "ingested_at": updated.isoformat(),
        "original_event": feature,
    }
    return json.dumps(message).encode()


def handle_all(test_database: str, messages: list[FakeMessage], country_id: str | None = "ESP") -> list[str]:
    settings = DatabaseSettings(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        database=test_database,
        user="observatory_writer",
        password=os.environ["DB_WRITER_PASSWORD"],
    )

    async def run() -> list[str]:
        pools = {
            "core": await open_pool(settings, "core", application_name="test-consumer"),
            "replay, core": await open_pool(settings, "replay, core", application_name="test-consumer-replay"),
        }
        try:
            handler = MessageHandler(pools, TOPICS, FixedCountry(country_id))
            return [await handler(message) for message in messages]
        finally:
            for pool in pools.values():
                await pool.close()

    return asyncio.run(run())


NOW = datetime.now(timezone.utc).replace(microsecond=0)


def test_valid_message_is_stored_with_its_provenance(test_database: str, owner_conn: psycopg.Connection) -> None:
    value = feature_message("E1", NOW - timedelta(hours=1), NOW - timedelta(minutes=50))
    assert handle_all(test_database, [FakeMessage("earthquakes.live", 7, value)]) == ["new"]

    row = owner_conn.execute(
        "SELECT source, country_id, magnitude, place FROM core.event_current WHERE event_id = 'E1'"
    ).fetchone()
    assert row == ("usgs_feed", "ESP", 4.2, "Test")
    payload, offset = owner_conn.execute("SELECT payload, kafka_offset FROM core.event_version").fetchone()
    assert payload["type"] == "Feature" and "original_event" not in payload
    assert offset == 7
    log = owner_conn.execute("SELECT outcome, produced_at IS NOT NULL FROM core.message_log").fetchone()
    assert log == ("new", True)


def test_reprocessing_the_same_message_changes_nothing(test_database: str, owner_conn: psycopg.Connection) -> None:
    value = feature_message("E1", NOW - timedelta(hours=1), NOW - timedelta(minutes=50))
    message = FakeMessage("earthquakes.live", 3, value)

    assert handle_all(test_database, [message, message, message]) == ["new", "duplicate", "duplicate"]
    counts = owner_conn.execute(
        "SELECT (SELECT count(*) FROM core.event_current), (SELECT count(*) FROM core.event_version),"
        " (SELECT count(*) FROM core.message_log)"
    ).fetchone()
    assert counts == (1, 1, 1)


def test_point_outside_every_polygon_has_no_country(test_database: str, owner_conn: psycopg.Connection) -> None:
    value = feature_message("SEA", NOW - timedelta(hours=1), NOW - timedelta(minutes=50))
    handle_all(test_database, [FakeMessage("earthquakes.live", 0, value)], country_id=None)
    assert owner_conn.execute("SELECT country_id FROM core.event_current").fetchone() == (None,)


@pytest.mark.parametrize("raw", [b"{not json", b'{"id": "E1", "mag": NaN}', b"\xff\xfe"], ids=["broken", "nan", "binary"])
def test_non_json_message_is_quarantined_as_text(test_database: str, owner_conn: psycopg.Connection, raw: bytes) -> None:
    assert handle_all(test_database, [FakeMessage("earthquakes.live", 0, raw)]) == ["quarantined"]

    row = owner_conn.execute("SELECT reason_codes, payload IS NULL, raw_text IS NOT NULL FROM core.quarantine").fetchone()
    assert row == (["malformed_json"], True, True)
    assert owner_conn.execute("SELECT outcome FROM core.message_log").fetchone() == ("quarantined",)


def test_version_refused_by_the_model_goes_to_quarantine_instead_of_blocking(
    test_database: str, owner_conn: psycopg.Connection
) -> None:
    # A catalog event from 1850 passes the consumer rules, but dim_date starts in 1900.
    old = datetime(1850, 6, 1, tzinfo=timezone.utc)
    following = feature_message("E2", NOW - timedelta(hours=1), NOW - timedelta(minutes=50))
    outcomes = handle_all(
        test_database,
        [
            FakeMessage("earthquakes.catalog", 0, feature_message("OLD", old, old)),
            FakeMessage("earthquakes.catalog", 1, following),
        ],
    )

    assert outcomes == ["quarantined", "new"]
    codes, event_id = owner_conn.execute("SELECT reason_codes, event_id FROM core.quarantine").fetchone()
    assert (codes, event_id) == (["model_constraint_violation"], "OLD")
    assert owner_conn.execute("SELECT count(*) FROM core.event_current WHERE event_id = 'OLD'").fetchone()[0] == 0


def test_replay_messages_land_only_in_replay(test_database: str, owner_conn: psycopg.Connection) -> None:
    original_time = datetime(2025, 3, 2, 4, 15, tzinfo=timezone.utc)
    value = feature_message("R1", original_time, original_time + timedelta(minutes=10))
    assert handle_all(test_database, [FakeMessage("earthquakes.replay", 0, value)]) == ["new"]

    row = owner_conn.execute(
        "SELECT source, event_time, replayed_at IS NOT NULL FROM replay.event_current WHERE event_id = 'R1'"
    ).fetchone()
    assert row == ("usgs_catalog", original_time, True)
    assert owner_conn.execute("SELECT count(*) FROM core.event_current").fetchone()[0] == 0
    assert owner_conn.execute("SELECT count(*) FROM replay.message_log").fetchone()[0] == 1
