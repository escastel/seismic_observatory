"""The core isolation check detects any change to real data and ignores replay_selection rows (R5)."""

from __future__ import annotations

from producer.app.replay.isolation import compare, load, save, take_snapshot
from tests.db.async_support import run_with_conn
from tests.db.helpers import Version, apply_version, utc


def snapshot(test_database: str) -> dict:
    return run_with_conn(test_database, take_snapshot)


def seed(owner_conn, count: int = 3) -> None:
    for n in range(count):
        apply_version(owner_conn, Version(f"I{n}", utc(f"2026-11-14 10:0{n}")))


def test_identical_without_changes(test_database, owner_conn) -> None:
    seed(owner_conn)
    first = snapshot(test_database)
    assert first["tables"]["event_current"]["rows"] == 3
    assert compare(first, snapshot(test_database)) == []


def test_detects_altered_row(test_database, owner_conn) -> None:
    seed(owner_conn)
    before = snapshot(test_database)
    owner_conn.execute("UPDATE core.event_current SET magnitude = magnitude + 1 WHERE event_id = 'I0'")
    differences = compare(before, snapshot(test_database))
    assert [d.table for d in differences] == ["event_current"]
    assert differences[0].before_rows == differences[0].after_rows


def test_detects_inserted_row(test_database, owner_conn) -> None:
    seed(owner_conn)
    before = snapshot(test_database)
    apply_version(owner_conn, Version("I99", utc("2026-11-14 11:00")))
    differences = compare(before, snapshot(test_database))
    assert "event_current" in [d.table for d in differences]
    current = next(d for d in differences if d.table == "event_current")
    assert (current.before_rows, current.after_rows) == (3, 4)


def test_detects_deleted_row(test_database, owner_conn) -> None:
    seed(owner_conn)
    before = snapshot(test_database)
    owner_conn.execute("DELETE FROM core.event_current WHERE event_id = 'I1'")
    differences = compare(before, snapshot(test_database))
    current = next(d for d in differences if d.table == "event_current")
    assert (current.before_rows, current.after_rows) == (3, 2)


def test_ignores_new_replay_selection_rows(test_database, owner_conn) -> None:
    before = snapshot(test_database)
    owner_conn.execute(
        """
        INSERT INTO core.extraction (source, purpose, request_url, requested_at, outcome)
        VALUES ('usgs_catalog', 'replay_selection', 'replay://selection', now(), 'ok')
        """
    )
    after = snapshot(test_database)
    assert compare(before, after) == []
    assert after["replay_selection_rows"] == before["replay_selection_rows"] + 1


def test_includes_table_created_in_the_test(test_database, owner_conn) -> None:
    owner_conn.execute("CREATE TABLE core.tmp_isolation_probe (id int)")
    owner_conn.execute("GRANT SELECT ON core.tmp_isolation_probe TO observatory_writer")
    try:
        before = snapshot(test_database)
        assert before["tables"]["tmp_isolation_probe"]["rows"] == 0
        owner_conn.execute("INSERT INTO core.tmp_isolation_probe VALUES (1)")
        differences = compare(before, snapshot(test_database))
        assert [d.table for d in differences] == ["tmp_isolation_probe"]
    finally:
        owner_conn.execute("DROP TABLE core.tmp_isolation_probe")


def test_save_and_load_round_trip(test_database, owner_conn, tmp_path) -> None:
    seed(owner_conn)
    taken = snapshot(test_database)
    path = tmp_path / "replay" / "core-snapshot.json"
    save(taken, path)
    assert b"\r\n" not in path.read_bytes()
    assert load(path) == taken
