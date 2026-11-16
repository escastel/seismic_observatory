"""Periodic purge of raw feed payloads (US5: FR-033, FR-034, SC-010)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from producer.app.main import purge_raw_payloads, purge_due
from tests.db.async_support import run_with_pool

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def test_purge_removes_only_old_feed_bodies(test_database, owner_conn, caplog) -> None:
    owner_conn.execute(
        "INSERT INTO core.raw_payload (content_sha256, encoding, body, byte_size, first_seen_at, last_seen_at) VALUES "
        "('old', 'gzip', '\\x00', 1, now() - interval '9 days', now() - interval '8 days'), "
        "('recent', 'gzip', '\\x00', 1, now() - interval '9 days', now() - interval '6 days')")
    owner_conn.execute(
        "INSERT INTO core.raw_payload (content_sha256, encoding, file_path, byte_size, first_seen_at, last_seen_at) "
        "VALUES ('catalog', 'file', 'usgs/catalog/x.geojson', 1, now() - interval '400 days', now() - interval '400 days')")
    for sha in ("old", "recent", "catalog"):
        owner_conn.execute("INSERT INTO core.extraction (source, purpose, request_url, requested_at, outcome, "
                           "content_sha256) VALUES ('usgs_feed', 'live', 'x', now() - interval '8 days', 'ok', %s)", (sha,))

    with caplog.at_level(logging.INFO):
        purged = run_with_pool(test_database, lambda pool: purge_raw_payloads(pool, 7))

    assert purged == 1
    remaining = {sha for (sha,) in owner_conn.execute("SELECT content_sha256 FROM core.raw_payload").fetchall()}
    assert remaining == {"recent", "catalog"}
    assert owner_conn.execute("SELECT count(*) FROM core.extraction").fetchone()[0] == 3
    assert owner_conn.execute("SELECT count(*) FROM core.extraction WHERE content_sha256 = 'old'").fetchone()[0] == 1
    assert any("Purged 1 raw payload(s)" in record.getMessage() for record in caplog.records)


def test_purge_failure_is_logged_and_does_not_raise(caplog) -> None:
    class BrokenPool:
        def acquire(self):
            raise ConnectionRefusedError("database is down")

    import asyncio

    with caplog.at_level(logging.WARNING):
        assert asyncio.run(purge_raw_payloads(BrokenPool(), 7)) is None
    assert any("purge" in record.getMessage().lower() for record in caplog.records)


def test_purge_runs_at_start_and_every_24_hours() -> None:
    assert purge_due(None, NOW)
    assert not purge_due(NOW - timedelta(hours=23, minutes=59), NOW)
    assert purge_due(NOW - timedelta(hours=24), NOW)
