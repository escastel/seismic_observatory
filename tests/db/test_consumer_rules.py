"""The consumer's quality rules end to end: the real MessageHandler against observatory_test.

Each case of tests/unit/test_rules.py ends in its table with its codes and flags
(specs/004-consumer-quality/data-model.md, section 2).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
import pytest

from .test_consumer_persistence import FakeMessage, handle_all

pytest.importorskip("geopandas")

NOW = datetime.now(timezone.utc).replace(microsecond=0)
DROP = object()


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def flat(event_id: str = "E1", **changes: Any) -> dict[str, Any]:
    """A valid producer message; changes replace top-level keys, DROP removes one."""
    event_time, updated = NOW - timedelta(hours=1), NOW - timedelta(minutes=50)
    geometry = {"type": "Point", "coordinates": [-3.7, 40.4, 10.0]}
    base: dict[str, Any] = {
        "id": event_id,
        "time": ms(event_time),
        "updated": ms(updated),
        "mag": 4.2,
        "place": "Test",
        "geometry": geometry,
        "properties": {"magType": "ml", "type": "earthquake"},
        "ingested_at": updated.isoformat(),
    }
    base["original_event"] = {"type": "Feature", "id": event_id, "geometry": geometry, "properties": {"mag": 4.2}}
    base.update(changes)
    return {key: value for key, value in base.items() if value is not DROP}


def coords(*values: Any) -> dict[str, Any]:
    return {"type": "Point", "coordinates": list(values)}


def send(test_database: str, payload: dict[str, Any] | bytes, topic: str = "earthquakes.live", **kwargs: Any) -> str:
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return handle_all(test_database, [FakeMessage(topic, 0, raw)], **kwargs)[0]


def current(conn: psycopg.Connection, event_id: str = "E1") -> tuple:
    return conn.execute(
        "SELECT magnitude, mag_type, depth_km, place, quality_flags FROM core.event_current WHERE event_id = %s",
        (event_id,),
    ).fetchone()


# ----- events: values and flags ----------------------------------------------------------------

EVENT_CASES = [
    ("null_magnitude", {"mag": None}, (None, "ml", 10.0, "Test", [])),
    ("null_type_depth_place", {"place": None, "geometry": coords(-3.7, 40.4, None), "properties": {"type": "earthquake"}}, (4.2, None, None, None, [])),
    ("negative_magnitude", {"mag": -0.5}, (-0.5, "ml", 10.0, "Test", [])),
    ("negative_depth", {"geometry": coords(-3.7, 40.4, -2.7)}, (4.2, "ml", -2.7, "Test", ["negative_depth"])),
    ("magnitude_high", {"mag": 10.5}, (10.5, "ml", 10.0, "Test", ["magnitude_out_of_range"])),
    ("magnitude_low", {"mag": -3}, (-3.0, "ml", 10.0, "Test", ["magnitude_out_of_range"])),
    ("deep", {"geometry": coords(-3.7, 40.4, 900)}, (4.2, "ml", 900.0, "Test", ["depth_out_of_range"])),
    ("old_event", {"time": ms(NOW - timedelta(days=30)), "updated": ms(NOW - timedelta(days=30))}, (4.2, "ml", 10.0, "Test", [])),
    ("future_10min", {"time": ms(NOW + timedelta(minutes=10)), "updated": ms(NOW + timedelta(minutes=10))}, (4.2, "ml", 10.0, "Test", ["future_time"])),
    ("future_2min", {"time": ms(NOW + timedelta(minutes=2)), "updated": ms(NOW + timedelta(minutes=2))}, (4.2, "ml", 10.0, "Test", [])),
    ("updated_before_time", {"updated": ms(NOW - timedelta(hours=2))}, (4.2, "ml", 10.0, "Test", ["updated_before_time"])),
    ("magnitude_text", {"mag": "4.2"}, (4.2, "ml", 10.0, "Test", ["magnitude_from_text"])),
    ("magnitude_garbage", {"mag": "abc"}, (None, "ml", 10.0, "Test", ["magnitude_not_numeric"])),
    ("extra_coordinates", {"geometry": coords(-3.7, 40.4, 10.0, 5.0)}, (4.2, "ml", 10.0, "Test", ["extra_coordinates"])),
    ("synthetic", {"synthetic": True}, (4.2, "ml", 10.0, "Test", ["synthetic"])),
]


@pytest.mark.parametrize(("name", "changes", "expected"), EVENT_CASES, ids=[case[0] for case in EVENT_CASES])
def test_tractable_message_becomes_an_event(
    test_database: str, owner_conn: psycopg.Connection, name: str, changes: dict[str, Any], expected: tuple
) -> None:
    assert send(test_database, flat(**changes)) == "new"
    assert current(owner_conn) == expected
    assert owner_conn.execute("SELECT count(*) FROM core.quarantine").fetchone()[0] == 0
    assert owner_conn.execute("SELECT outcome FROM core.message_log").fetchone() == ("new",)


def test_ambiguous_country_adds_its_flag_to_the_other_flags(test_database: str, owner_conn: psycopg.Connection) -> None:
    send(test_database, flat(mag=-3), ambiguous=True)
    assert current(owner_conn)[4] == ["ambiguous_country", "magnitude_out_of_range"]


def test_revision_replaces_the_flags(test_database: str, owner_conn: psycopg.Connection) -> None:
    first = flat(mag=-3)
    second = flat(mag=4.0, updated=ms(NOW - timedelta(minutes=5)))
    handle_all(
        test_database,
        [FakeMessage("earthquakes.live", 0, json.dumps(first).encode()), FakeMessage("earthquakes.live", 1, json.dumps(second).encode())],
    )
    assert current(owner_conn) == (4.0, "ml", 10.0, "Test", [])


# ----- quarantine ------------------------------------------------------------------------------

QUARANTINE_CASES = [
    ("missing_id", flat(id=DROP)),
    ("invalid_id", flat(id=5)),
    ("missing_time", flat(time=DROP)),
    ("invalid_time", flat(time="x")),
    ("missing_updated", flat(updated=DROP)),
    ("invalid_updated", flat(updated="x")),
    ("geometry_missing", flat(geometry=DROP)),
    ("geometry_not_point", flat(geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]})),
    ("coordinates_missing", flat(geometry={"type": "Point"})),
    ("coordinates_not_numeric", flat(geometry=coords("a", 40))),
    ("coordinates_out_of_range", flat(geometry=coords(-3.7, 145, 1))),
    ("coordinates_out_of_range", flat(geometry=coords(-200, 40, 1))),
]


@pytest.mark.parametrize(("code", "payload"), QUARANTINE_CASES)
def test_intractable_message_goes_to_quarantine(
    test_database: str, owner_conn: psycopg.Connection, code: str, payload: dict[str, Any]
) -> None:
    assert send(test_database, payload) == "quarantined"
    row = owner_conn.execute("SELECT reason_codes, payload IS NOT NULL, is_synthetic FROM core.quarantine").fetchone()
    assert row == ([code], True, False)
    assert owner_conn.execute("SELECT count(*) FROM core.event_current").fetchone()[0] == 0
    assert owner_conn.execute("SELECT outcome FROM core.message_log").fetchone() == ("quarantined",)


def test_overflowing_coordinate_is_quarantined(test_database: str, owner_conn: psycopg.Connection) -> None:
    raw = json.dumps(flat(geometry=coords(0, 40))).replace('"coordinates": [0, 40]', '"coordinates": [1e999, 40]').encode()
    assert send(test_database, raw) == "quarantined"
    row = owner_conn.execute("SELECT reason_codes, payload IS NULL, raw_text IS NOT NULL FROM core.quarantine").fetchone()
    assert row == (["coordinates_not_finite"], True, True)


def test_json_that_is_not_an_object_is_quarantined(test_database: str, owner_conn: psycopg.Connection) -> None:
    assert send(test_database, b"[1, 2]") == "quarantined"
    assert owner_conn.execute("SELECT reason_codes, payload FROM core.quarantine").fetchone() == (["not_an_object"], [1, 2])


def test_several_reasons_make_one_row_with_all_of_them(test_database: str, owner_conn: psycopg.Connection) -> None:
    payload = flat(id=DROP, time="x", updated=DROP, geometry=coords(-3.7, 145))
    assert send(test_database, payload) == "quarantined"
    rows = owner_conn.execute("SELECT reason_codes, reason_detail FROM core.quarantine").fetchall()
    assert len(rows) == 1
    codes, detail = rows[0]
    assert codes == ["missing_id", "invalid_time", "missing_updated", "coordinates_out_of_range"]
    assert all(code in detail for code in codes)
    assert owner_conn.execute("SELECT count(*) FROM core.message_log").fetchone()[0] == 1


def test_synthetic_quarantine_row_is_marked(test_database: str, owner_conn: psycopg.Connection) -> None:
    send(test_database, flat(id=DROP, synthetic=True))
    assert owner_conn.execute("SELECT is_synthetic FROM core.quarantine").fetchone() == (True,)


def test_model_rejection_keeps_the_database_error_and_the_next_message_goes_on(
    test_database: str, owner_conn: psycopg.Connection
) -> None:
    old = datetime(1850, 6, 1, tzinfo=timezone.utc)
    started = time.monotonic()
    outcomes = handle_all(
        test_database,
        [
            FakeMessage("earthquakes.live", 0, json.dumps(flat("OLD", time=ms(old), updated=ms(old))).encode()),
            FakeMessage("earthquakes.live", 1, json.dumps(flat("NEXT")).encode()),
        ],
    )
    assert outcomes == ["quarantined", "new"]
    assert time.monotonic() - started < 1.0 + 5  # no retry loop; generous margin for pool start-up
    codes, detail, is_synthetic = owner_conn.execute("SELECT reason_codes, reason_detail, is_synthetic FROM core.quarantine").fetchone()
    assert codes == ["model_constraint_violation"] and is_synthetic is False
    assert "Error" in detail  # the asyncpg exception text travels in the detail
    assert owner_conn.execute("SELECT count(*) FROM core.event_current WHERE event_id = 'NEXT'").fetchone()[0] == 1


# ----- exclusion -------------------------------------------------------------------------------


def test_other_event_type_is_excluded_once(test_database: str, owner_conn: psycopg.Connection) -> None:
    payload = flat("QB", properties={"type": "quarry blast"})
    raw = json.dumps(payload).encode()
    outcomes = handle_all(test_database, [FakeMessage("earthquakes.live", 0, raw), FakeMessage("earthquakes.live", 1, raw)])
    assert outcomes == ["excluded", "excluded"]
    row = owner_conn.execute("SELECT event_id, event_type, reason_code, extraction_id FROM core.excluded_event").fetchone()
    assert row == ("QB", "quarry blast", "not_earthquake", None)
    assert owner_conn.execute("SELECT count(*) FROM core.excluded_event").fetchone()[0] == 1
    assert owner_conn.execute("SELECT count(*) FROM core.event_current").fetchone()[0] == 0
    assert owner_conn.execute("SELECT outcome, count(*) FROM core.message_log GROUP BY outcome").fetchall() == [("excluded", 2)]


def test_missing_type_is_excluded(test_database: str, owner_conn: psycopg.Connection) -> None:
    assert send(test_database, flat("NT", properties={"magType": "ml"})) == "excluded"
    assert owner_conn.execute("SELECT reason_code, event_type FROM core.excluded_event").fetchone() == ("missing_type", None)


def test_exclusion_with_unknown_extraction_does_not_fail(test_database: str, owner_conn: psycopg.Connection) -> None:
    assert send(test_database, flat("QB2", properties={"type": "explosion"}, extraction_id=987654)) == "excluded"
    assert owner_conn.execute("SELECT extraction_id FROM core.excluded_event").fetchone() == (None,)


# ----- topics ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("topic", "schema"),
    [("earthquakes.live", "core"), ("earthquakes.catalog", "core"), ("earthquakes.replay", "replay")],
)
def test_the_three_topics_apply_the_same_rules(
    test_database: str, owner_conn: psycopg.Connection, topic: str, schema: str
) -> None:
    old = NOW - timedelta(days=400)
    messages = [
        FakeMessage(topic, 0, json.dumps(flat("A", mag=None, time=ms(old), updated=ms(old))).encode()),
        FakeMessage(topic, 1, json.dumps(flat("B", geometry=coords(-3.7, 40.4, -1))).encode()),
        FakeMessage(topic, 2, json.dumps(flat("C", geometry=coords(-3.7, 145))).encode()),
        FakeMessage(topic, 3, json.dumps(flat("D", properties={"type": "explosion"})).encode()),
    ]
    assert handle_all(test_database, messages) == ["new", "new", "quarantined", "excluded"]
    rows = owner_conn.execute(f"SELECT event_id, magnitude, quality_flags FROM {schema}.event_current ORDER BY event_id").fetchall()
    assert rows == [("A", None, []), ("B", 4.2, ["negative_depth"])]
    assert owner_conn.execute(f"SELECT event_id FROM {schema}.quarantine").fetchall() == [("C",)]
    assert owner_conn.execute(f"SELECT event_id FROM {schema}.excluded_event").fetchall() == [("D",)]
    other = "replay" if schema == "core" else "core"
    assert owner_conn.execute(f"SELECT count(*) FROM {other}.event_current").fetchone()[0] == 0


def test_a_defective_message_does_not_delay_the_next_one(test_database: str) -> None:
    messages = [FakeMessage("earthquakes.live", 0, b"{broken"), FakeMessage("earthquakes.live", 1, json.dumps(flat()).encode())]
    started = time.monotonic()
    assert handle_all(test_database, messages) == ["quarantined", "new"]
    assert time.monotonic() - started < 1.0 + 5


def test_a_synthetic_key_marks_a_message_whose_body_cannot_be_read(test_database: str, owner_conn: psycopg.Connection) -> None:
    """FR-025: unreadable JSON cannot carry the marker; the Kafka key (the event id) does."""
    class Keyed(FakeMessage):
        key = b"synthetic-malformed_json"

    from .test_consumer_persistence import handle_all as run_handler

    run_handler(test_database, [Keyed("earthquakes.live", 0, b"{truncated"), FakeMessage("earthquakes.live", 1, b"{truncated")])

    rows = owner_conn.execute("SELECT kafka_offset, is_synthetic FROM core.quarantine ORDER BY kafka_offset").fetchall()
    assert rows == [(0, True), (1, False)]


def test_a_synthetic_key_adds_the_flag_to_a_readable_event(test_database: str, owner_conn: psycopg.Connection) -> None:
    class Keyed(FakeMessage):
        key = b"synthetic-keyed"

    from .test_consumer_persistence import handle_all as run_handler

    run_handler(test_database, [Keyed("earthquakes.live", 0, json.dumps(flat("synthetic-keyed")).encode())])
    assert current(owner_conn, "synthetic-keyed")[4] == ["synthetic"]
