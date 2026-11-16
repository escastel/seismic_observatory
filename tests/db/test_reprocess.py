"""Reprocessing of the quarantine against the real model (contracts/reprocess.md)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
import pytest

pytest.importorskip("geopandas")

from common.db import open_pool  # noqa: E402
from common.settings import TopicNames  # noqa: E402
from consumer.app.reprocess import reprocess  # noqa: E402

from .async_support import writer_settings  # noqa: E402
from .helpers import Message, Version, apply_version, quarantine, utc  # noqa: E402
from .test_consumer_persistence import FixedCountry  # noqa: E402

TOPICS = TopicNames()
NOW = datetime.now(timezone.utc).replace(microsecond=0)
LIVE, REPLAY = TOPICS.live, TOPICS.replay


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def message(event_id: str = "E1", **changes: Any) -> dict[str, Any]:
    updated = changes.pop("updated_at", NOW - timedelta(minutes=50))
    geometry = {"type": "Point", "coordinates": [-3.7, 40.4, 10.0]}
    base = {
        "id": event_id, "time": ms(NOW - timedelta(hours=1)), "updated": ms(updated), "mag": 4.2, "place": "Test",
        "geometry": geometry, "properties": {"magType": "ml", "type": "earthquake"},
        "ingested_at": updated.isoformat(),
        "original_event": {"type": "Feature", "id": event_id, "geometry": geometry, "properties": {"mag": 4.2}},
    }
    base.update(changes)
    return base


def seed(conn: psycopg.Connection, topic: str, offset: int, codes: list[str], payload: dict | None = None,
         raw_text: str | None = None, synthetic: bool = False) -> None:
    """A quarantined message with its attempt 0 log row, in the schema of its topic."""
    schema = "replay" if topic == REPLAY else "core"
    conn.execute(f"SET search_path = {schema}, core")
    event_id = payload.get("id") if payload else None
    quarantine(conn, Message(topic, 0, offset), codes, event_id=event_id, payload=payload, raw_text=raw_text, is_synthetic=synthetic)
    conn.execute(
        "INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, event_id, outcome) VALUES (%s, 0, %s, %s, 'quarantined')",
        (topic, offset, event_id),
    )
    conn.execute("SET search_path = core")


def run(test_database: str, *, dry_run: bool = False, runs: int = 1, country: str | None = "ESP") -> list[Any]:
    async def main() -> list[Any]:
        settings = writer_settings(test_database)
        sets = []
        for _ in range(runs):
            sets.append({
                "core": await open_pool(settings, "core", application_name="t", max_size=2),
                "replay, core": await open_pool(settings, "replay, core", application_name="t", max_size=2),
            })
        lines: list[str] = []
        try:
            return await asyncio.gather(
                *(reprocess(pools, TOPICS, FixedCountry(country), dry_run=dry_run, out=lines.append) for pools in sets)
            )
        finally:
            for pools in sets:
                for pool in pools.values():
                    await pool.close()

    return asyncio.run(main())


def counts(conn: psycopg.Connection) -> tuple:
    return conn.execute(
        """SELECT (SELECT count(*) FROM core.quarantine), (SELECT count(*) FROM core.message_log),
                  (SELECT count(*) FROM core.event_current), (SELECT count(*) FROM core.event_version),
                  (SELECT count(*) FROM replay.quarantine), (SELECT count(*) FROM replay.message_log),
                  (SELECT count(*) FROM replay.event_current)"""
    ).fetchone()


def one(conn: psycopg.Connection, query: str) -> Any:
    return conn.execute(query).fetchone()


def test_null_magnitude_row_is_recovered_in_core(test_database: str, owner_conn: psycopg.Connection) -> None:
    seed(owner_conn, LIVE, 1, ["magnitude_null"], message(mag=None))
    [summary] = run(test_database)
    assert (summary.pending, summary.recovered, summary.still_rejected) == (1, 1, 0)

    assert one(owner_conn, "SELECT magnitude, country_id FROM core.event_current WHERE event_id = 'E1'") == (None, "ESP")
    row = one(owner_conn, "SELECT reprocess_result, reprocessed_at IS NOT NULL, reprocess_reason_codes FROM core.quarantine")
    assert row == ("recovered_new", True, None)
    log = owner_conn.execute("SELECT attempt, outcome FROM core.message_log ORDER BY attempt").fetchall()
    assert log == [(0, "quarantined"), (1, "new")]
    assert one(owner_conn, "SELECT count(*) FROM replay.event_current")[0] == 0


def test_invalid_coordinates_stay_rejected_with_their_reasons(test_database: str, owner_conn: psycopg.Connection) -> None:
    bad = message(geometry={"type": "Point", "coordinates": [-3.7, 145.0, 1.0]})
    seed(owner_conn, LIVE, 1, ["coordinates_out_of_range"], bad)
    [summary] = run(test_database)
    assert (summary.recovered, summary.still_rejected) == (0, 1)
    row = one(owner_conn, "SELECT reprocess_result, reprocess_reason_codes FROM core.quarantine")
    assert row == ("still_rejected", ["coordinates_out_of_range"])
    assert one(owner_conn, "SELECT count(*) FROM core.event_current")[0] == 0
    assert one(owner_conn, "SELECT count(*) FROM core.message_log WHERE attempt = 1")[0] == 1


def test_raw_text_row_stays_rejected(test_database: str, owner_conn: psycopg.Connection) -> None:
    seed(owner_conn, LIVE, 1, ["malformed_json"], raw_text='{"id": "E1", ')
    run(test_database)
    row = one(owner_conn, "SELECT reprocess_result, reprocess_reason_codes, raw_text FROM core.quarantine")
    assert row == ("still_rejected", ["malformed_json"], '{"id": "E1", ')


def test_second_run_changes_nothing(test_database: str, owner_conn: psycopg.Connection) -> None:
    seed(owner_conn, LIVE, 1, ["magnitude_null"], message(mag=None))
    seed(owner_conn, LIVE, 2, ["x"], raw_text="nope")
    seed(owner_conn, REPLAY, 1, ["magnitude_null"], message("R1", mag=None))
    run(test_database)
    before = counts(owner_conn)
    stamps = owner_conn.execute("SELECT reprocessed_at FROM core.quarantine ORDER BY quarantine_id").fetchall()
    [summary] = run(test_database)
    assert summary.pending == 0
    assert counts(owner_conn) == before
    assert owner_conn.execute("SELECT reprocessed_at FROM core.quarantine ORDER BY quarantine_id").fetchall() == stamps


def test_replay_row_recovers_into_replay(test_database: str, owner_conn: psycopg.Connection) -> None:
    seed(owner_conn, REPLAY, 5, ["magnitude_null"], message("R1", mag=None))
    run(test_database)
    assert one(owner_conn, "SELECT replayed_at IS NOT NULL FROM replay.event_current WHERE event_id = 'R1'") == (True,)
    assert one(owner_conn, "SELECT count(*) FROM core.event_current")[0] == 0
    assert one(owner_conn, "SELECT reprocess_result FROM replay.quarantine") == ("recovered_new",)
    assert owner_conn.execute("SELECT attempt FROM replay.message_log ORDER BY attempt").fetchall() == [(0,), (1,)]


def test_later_version_already_present_gives_stale(test_database: str, owner_conn: psycopg.Connection) -> None:
    later = utc((NOW - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"))
    apply_version(owner_conn, Version("E1", later, event_time=NOW - timedelta(hours=1), magnitude=5.5), Message(LIVE, 0, 99))
    seed(owner_conn, LIVE, 1, ["magnitude_null"], message(mag=None, updated_at=NOW - timedelta(minutes=50)))
    run(test_database)
    assert one(owner_conn, "SELECT reprocess_result FROM core.quarantine") == ("recovered_stale",)
    assert one(owner_conn, "SELECT magnitude, updated_at FROM core.event_current WHERE event_id = 'E1'") == (5.5, later)
    assert one(owner_conn, "SELECT count(*) FROM core.event_version")[0] == 2


def test_synthetic_row_recovers_with_the_synthetic_flag(test_database: str, owner_conn: psycopg.Connection) -> None:
    payload = message("synthetic-x", mag=None, synthetic=True, synthetic_case="x")
    seed(owner_conn, LIVE, 1, ["magnitude_null"], payload, synthetic=True)
    run(test_database)
    assert one(owner_conn, "SELECT quality_flags FROM core.event_current WHERE event_id = 'synthetic-x'") == (["synthetic"],)
    assert one(owner_conn, "SELECT is_synthetic, reprocess_result FROM core.quarantine") == (True, "recovered_new")


def test_dry_run_writes_nothing(test_database: str, owner_conn: psycopg.Connection) -> None:
    seed(owner_conn, LIVE, 1, ["magnitude_null"], message(mag=None))
    seed(owner_conn, REPLAY, 1, ["magnitude_null"], message("R1", mag=None))
    before = counts(owner_conn)
    [summary] = run(test_database, dry_run=True)
    assert summary.pending == 2 and summary.recovered == 2
    assert counts(owner_conn) == before
    assert one(owner_conn, "SELECT count(*) FROM core.quarantine WHERE reprocessed_at IS NULL")[0] == 1


def test_exclusion_is_recovered_as_excluded(test_database: str, owner_conn: psycopg.Connection) -> None:
    seed(owner_conn, LIVE, 1, ["x"], message(properties={"type": "explosion"}))
    run(test_database)
    assert one(owner_conn, "SELECT count(*) FROM core.excluded_event")[0] == 1
    assert one(owner_conn, "SELECT reprocess_result FROM core.quarantine") == ("recovered_new",)
    assert one(owner_conn, "SELECT outcome FROM core.message_log WHERE attempt = 1") == ("excluded",)


def test_model_refusal_stays_rejected(test_database: str, owner_conn: psycopg.Connection) -> None:
    old = message(time=-2_800_000_000_000, updated=-2_799_999_000_000)
    seed(owner_conn, LIVE, 1, ["x"], old)
    run(test_database)
    row = one(owner_conn, "SELECT reprocess_result, reprocess_reason_codes FROM core.quarantine")
    assert row == ("still_rejected", ["model_constraint_violation"])
    assert one(owner_conn, "SELECT count(*) FROM core.event_current")[0] == 0


def test_two_concurrent_runs_end_like_one(test_database: str, owner_conn: psycopg.Connection) -> None:
    for offset in range(1, 7):
        seed(owner_conn, LIVE, offset, ["magnitude_null"], message(f"E{offset}", mag=None))
    seed(owner_conn, REPLAY, 1, ["magnitude_null"], message("R1", mag=None))
    seed(owner_conn, LIVE, 20, ["x"], raw_text="nope")
    summaries = run(test_database, runs=2)
    assert sum(s.recovered for s in summaries) == 7 and sum(s.still_rejected for s in summaries) == 1
    assert one(owner_conn, "SELECT count(*) FROM core.event_current")[0] == 6
    assert one(owner_conn, "SELECT count(*) FROM core.message_log WHERE attempt = 1")[0] == 7
    assert one(owner_conn, "SELECT count(*) FROM core.quarantine WHERE reprocessed_at IS NULL")[0] == 0
    assert one(owner_conn, "SELECT count(*) FROM replay.message_log WHERE attempt = 1")[0] == 1
