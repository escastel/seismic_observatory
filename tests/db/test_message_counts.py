"""Model changes of spec 004: reprocessing columns, message_log attempt and the excluded outcome."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

from tests.db.helpers import MESSAGE_LOG_SQL, Message, quarantine, utc

APPLY = Path(__file__).resolve().parents[2] / "db" / "sql" / "apply.sh"
LOG_ROW = ("earthquakes.live", 0, 5, "E1", None, "quarantined", None)


@pytest.mark.parametrize("schema", ["core", "replay"])
def test_original_and_reprocessed_rows_coexist_but_not_twice(connect, schema: str) -> None:
    conn = connect("writer", search_path=schema)
    conn.execute("INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, outcome, attempt) "
                 "VALUES ('t', 0, 5, 'quarantined', 0)")
    conn.execute("INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, outcome, attempt) "
                 "VALUES ('t', 0, 5, 'new', 1)")
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute("INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, outcome, attempt) "
                     "VALUES ('t', 0, 5, 'new', 1)")
    assert conn.execute("SELECT outcome FROM message_log ORDER BY attempt").fetchall() == [("quarantined",), ("new",)]


def test_helper_insert_is_idempotent_per_attempt(writer_conn: psycopg.Connection) -> None:
    for _ in range(3):
        writer_conn.execute(MESSAGE_LOG_SQL, LOG_ROW)
    assert writer_conn.execute("SELECT count(*), min(attempt) FROM message_log").fetchone() == (1, 0)


def test_excluded_outcome_is_accepted(writer_conn: psycopg.Connection) -> None:
    writer_conn.execute("INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, outcome) "
                        "VALUES ('t', 0, 1, 'excluded')")
    with pytest.raises(psycopg.errors.CheckViolation):
        writer_conn.execute("INSERT INTO message_log (kafka_topic, kafka_partition, kafka_offset, outcome) "
                            "VALUES ('t', 0, 2, 'ignored')")


def test_reprocess_columns_are_validated(writer_conn: psycopg.Connection) -> None:
    quarantine(writer_conn, Message("earthquakes.live", 0, 1), ["magnitude_null"], payload={"id": "E1"})
    update = "UPDATE quarantine SET reprocessed_at = now(), reprocess_result = %s"

    with pytest.raises(psycopg.errors.CheckViolation):
        writer_conn.execute(update, ("done",))
    with pytest.raises(psycopg.errors.CheckViolation):
        writer_conn.execute("UPDATE quarantine SET reprocessed_at = now()")
    with pytest.raises(psycopg.errors.CheckViolation):
        writer_conn.execute("UPDATE quarantine SET reprocess_result = 'still_rejected'")

    writer_conn.execute(update + ", reprocess_reason_codes = %s", ("still_rejected", ["coordinates_out_of_range"]))
    assert writer_conn.execute("SELECT reprocess_result, reprocess_reason_codes FROM quarantine").fetchone() == (
        "still_rejected", ["coordinates_out_of_range"])


def test_new_quarantine_rows_start_unreprocessed(writer_conn: psycopg.Connection) -> None:
    quarantine(writer_conn, Message("earthquakes.live", 0, 1), ["invalid_json"], raw_text="{")
    assert writer_conn.execute(
        "SELECT reprocessed_at, reprocess_result, reprocess_reason_codes FROM quarantine").fetchone() == (None, None, None)


def test_the_migration_can_be_applied_again_to_an_existing_database(test_database: str, owner_conn) -> None:
    """041 is idempotent: applying it to a database that already has it changes nothing."""
    owner_conn.execute("INSERT INTO core.message_log (kafka_topic, kafka_partition, kafka_offset, outcome, attempt) "
                       "VALUES ('keep', 0, 1, 'new', 0)")
    for _ in range(2):
        result = subprocess.run([str(APPLY), test_database, "041_consumer_quality.sql"], capture_output=True,
                                text=True, env={**os.environ}, check=False)
        assert result.returncode == 0, result.stderr
    assert owner_conn.execute("SELECT count(*) FROM core.message_log WHERE kafka_topic = 'keep'").fetchone() == (1,)
    pk = owner_conn.execute(
        "SELECT array_agg(a.attname ORDER BY a.attnum) FROM pg_index i JOIN pg_attribute a "
        "ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey) "
        "WHERE i.indrelid = 'core.message_log'::regclass AND i.indisprimary").fetchone()[0]
    assert pk == ["kafka_topic", "kafka_partition", "kafka_offset", "attempt"]


def test_the_old_primary_key_is_upgraded_in_place(owner_conn) -> None:
    """A database created before spec 004 (key without attempt) is upgraded keeping its rows."""
    owner_conn.execute("INSERT INTO core.message_log (kafka_topic, kafka_partition, kafka_offset, outcome) "
                       "VALUES ('old', 0, 9, 'new')")
    owner_conn.execute("ALTER TABLE core.message_log DROP CONSTRAINT message_log_pkey")
    owner_conn.execute("ALTER TABLE core.message_log ADD PRIMARY KEY (kafka_topic, kafka_partition, kafka_offset)")
    owner_conn.execute("ALTER TABLE core.message_log DROP COLUMN attempt")

    result = subprocess.run([str(APPLY), os.environ.get("TEST_DATABASE", "observatory_test"), "041_consumer_quality.sql"],
                            capture_output=True, text=True, env={**os.environ}, check=False)

    assert result.returncode == 0, result.stderr
    assert owner_conn.execute("SELECT kafka_topic, attempt FROM core.message_log WHERE kafka_topic = 'old'").fetchone() == ("old", 0)
