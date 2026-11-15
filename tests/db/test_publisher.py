"""Version publication rules shared by feed and catalog (FR-008, FR-008a, FR-009; FAQ 10)."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import psycopg
import pytest

from producer.app.classify import classify
from producer.app.publisher import build_message, encode, publish_versions
from tests.db.async_support import run_with_conn
from tests.support.fake_kafka import FakeProducer
from tests.support.usgs_stub import feature

TOPIC = "earthquakes.live"
NOW = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)


def items(*features):
    return classify(list(features)).earthquakes


def publish(test_database, producer, features, source="usgs_feed", extraction_id=7):
    return run_with_conn(
        test_database,
        lambda conn: publish_versions(producer, conn, TOPIC, items(*features), source=source,
                                      extraction_id=extraction_id, now=lambda: NOW),
    )


def state(owner_conn: psycopg.Connection) -> dict[str, datetime]:
    return dict(owner_conn.execute("SELECT event_id, updated_at FROM core.publish_state").fetchall())


def test_new_version_is_published_and_marked(test_database, owner_conn) -> None:
    producer = FakeProducer()
    outcome = publish(test_database, producer, [feature("E1", updated="2026-11-15T09:00:00Z")])

    assert (outcome.published, outcome.pending, outcome.error) == (1, [], None)
    assert producer.keys() == ["E1"]
    assert state(owner_conn) == {"E1": datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)}


def test_same_or_older_version_is_not_published_again(test_database) -> None:
    producer = FakeProducer()
    publish(test_database, producer, [feature("E1", updated="2026-11-15T09:05:00Z")])

    same = publish(test_database, producer, [feature("E1", updated="2026-11-15T09:05:00Z")])
    older = publish(test_database, producer, [feature("E1", updated="2026-11-15T09:00:00Z")], source="usgs_catalog")

    assert (same.published, older.published) == (0, 0)
    assert producer.keys() == ["E1"]


def test_later_version_is_published(test_database, owner_conn) -> None:
    producer = FakeProducer()
    publish(test_database, producer, [feature("E1", updated="2026-11-15T09:00:00Z")])
    revised = publish(test_database, producer, [feature("E1", updated="2026-11-15T09:10:00Z", mag=4.6)])

    assert revised.published == 1
    assert producer.sent[-1].value["mag"] == 4.6
    assert state(owner_conn)["E1"] == datetime(2026, 11, 15, 9, 10, tzinfo=timezone.utc)


def test_failed_send_leaves_the_rest_pending_and_unmarked(test_database, owner_conn) -> None:
    features = [feature(f"E{n}", updated=f"2026-11-15T09:0{n}:00Z") for n in range(3)]

    first = publish(test_database, FakeProducer(fail_after=1), features)

    assert first.published == 1
    assert [item.event_id for item in first.pending] == ["E1", "E2"]
    assert isinstance(first.error, ConnectionError)
    assert set(state(owner_conn)) == {"E0"}

    retry = FakeProducer()
    second = publish(test_database, retry, features)
    assert second.published == 2
    assert retry.keys() == ["E1", "E2"]


def test_repeated_event_in_one_batch_publishes_its_latest_version_once(test_database) -> None:
    producer = FakeProducer()
    outcome = publish(test_database, producer, [
        feature("E1", updated="2026-11-15T09:00:00Z", mag=4.0),
        feature("E1", updated="2026-11-15T09:10:00Z", mag=4.4),
    ])

    assert outcome.published == 1
    assert producer.sent[0].value["mag"] == 4.4


def test_message_contract(test_database) -> None:
    producer = FakeProducer()
    original = feature("us7000abcd", time="2026-11-15T08:00:00Z", updated="2026-11-15T08:05:00Z", mag=4.6, place="Somewhere")
    publish(test_database, producer, [original], source="usgs_catalog", extraction_id=1234)

    sent = producer.sent[0]
    assert sent.key == "us7000abcd" and sent.topic == TOPIC
    value = sent.value
    assert value["source"] == "usgs_catalog"
    assert value["mode"] == "live"
    assert value["extraction_id"] == 1234
    assert value["ingested_at"] == "2026-11-15T10:00:00+00:00"
    assert value["original_event"] == original
    assert (value["id"], value["mag"], value["place"]) == ("us7000abcd", 4.6, "Somewhere")
    assert value["time"] == original["properties"]["time"]
    assert value["updated"] == original["properties"]["updated"]
    assert value["geometry"] == original["geometry"]
    assert value["properties"] == original["properties"]


def test_messages_never_contain_nan() -> None:
    broken = feature("E1")
    broken["properties"]["mag"] = math.nan
    with pytest.raises(ValueError):
        encode(build_message(broken, source="usgs_feed", extraction_id=1, ingested_at=NOW))
    assert json.loads(encode(build_message(feature("E2"), source="usgs_feed", extraction_id=1, ingested_at=NOW)))
