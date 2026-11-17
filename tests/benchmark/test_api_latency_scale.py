"""Behaviour of the API scale benchmark (spec 008, T014) with a tiny size. Synthetic data only."""

from __future__ import annotations

import psycopg

from tests.benchmark.api_latency_scale import main
from tests.benchmark.index_benchmark import SCHEMA, conninfo


def _schema_exists() -> bool:
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        row = conn.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (SCHEMA,)).fetchone()
    return row is not None


def _core_event_count() -> int:
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        return conn.execute("SELECT count(*) FROM core.event_current").fetchone()[0]


def test_small_run_succeeds_and_leaves_core_and_bench_untouched(capsys) -> None:
    before = _core_event_count()

    code = main(["--size", "2000", "--runs", "2", "--warmup", "1", "--indexes"])

    output = capsys.readouterr().out
    assert code == 0
    assert "with secondary indexes" in output
    assert "events limit=10" in output and "statistics (2025, no filter)" in output
    assert not _schema_exists()
    assert _core_event_count() >= before  # the live feed may add rows, but nothing is removed
