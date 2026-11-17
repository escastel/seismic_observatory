"""Behaviour of the structure benchmark (spec 008, T012) with tiny sizes. Synthetic data only."""

from __future__ import annotations

import psycopg
import pytest

from tests.benchmark.index_benchmark import SCHEMA, conninfo
from tests.benchmark.structure_benchmark import markdown, run_benchmark

EXPECTED = {
    "search": {"list_scan", "dict", "sql_no_key", "sql_primary_key"},
    "geo": {"naive_polygons", "strtree"},
    "hourly": {"python_dict", "sql_date_bin"},
}
SIZES = [200, 500]


@pytest.fixture(scope="module")
def report() -> dict:
    return run_benchmark(SIZES, repeats=1, lookups=20)


def test_every_operation_and_variant_is_measured_at_every_size(report: dict) -> None:
    assert report["synthetic"] is True
    for size in SIZES:
        for operation, variants in EXPECTED.items():
            found = {r["variant"] for r in report["results"] if r["operation"] == operation and r["size"] == size}
            assert found == variants, (operation, size)
    assert all(r["median_ms"] >= 0 and r["repeats"] == 1 for r in report["results"])


def test_variants_of_an_operation_return_the_same_result(report: dict) -> None:
    for size in SIZES:
        for operation in EXPECTED:
            rows = [r for r in report["results"] if r["operation"] == operation and r["size"] == size]
            assert all(r["identical"] for r in rows), (operation, size)
            assert len({r["digest"] for r in rows}) == 1, (operation, size)


def test_markdown_marks_the_data_as_synthetic(report: dict) -> None:
    text = markdown(report)
    assert "SINTÉTICO" in text
    for operation in EXPECTED:
        assert f"## `{operation}`" in text


def test_bench_schema_does_not_exist_afterwards(report: dict) -> None:
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        found = conn.execute("SELECT count(*) FROM pg_namespace WHERE nspname = %s", (SCHEMA,)).fetchone()[0]
    assert found == 0
