"""Reproducible local benchmark for algorithm and query scaling."""

from __future__ import annotations

import statistics
import time
import tracemalloc
from os import getenv


def benchmark(size: int) -> dict[str, float | int]:
    records = [{"id": f"event-{index}", "value": index} for index in range(size)]
    lookup = {record["id"]: record for record in records}
    probes = [f"event-{index}" for index in range(0, size, max(1, size // 100))]

    started = time.perf_counter()
    for probe in probes:
        next(record for record in records if record["id"] == probe)
    sequential_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    for probe in probes:
        lookup[probe]
    indexed_ms = (time.perf_counter() - started) * 1000

    tracemalloc.start()
    _ = [{"id": record["id"], "value": record["value"]} for record in records]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "size": size,
        "sequential_ms": round(sequential_ms, 3),
        "indexed_ms": round(indexed_ms, 3),
        "peak_bytes": peak,
    }


def run_benchmark() -> list[dict[str, float | int]]:
    return [benchmark(size) for size in (100, 1000, 10000)]


def benchmark_postgres_indexes() -> dict[str, float | str]:
    """Measure indexed and sequential plans when a test database is available."""
    dsn = getenv("TEST_DATABASE_DSN")
    if not dsn:
        return {"status": "skipped", "reason": "TEST_DATABASE_DSN is not configured"}
    try:
        import psycopg2
    except ImportError:
        return {"status": "skipped", "reason": "psycopg2 is not installed"}

    queries = {
        "indexed": (
            "SELECT COUNT(*) FROM fact_sismos "
            "WHERE event_time >= CURRENT_DATE - INTERVAL '30 days'"
        ),
        "country_indexed": (
            "SELECT COUNT(*) FROM fact_sismos f "
            "JOIN dim_geografia g ON g.geografia_key=f.geografia_key "
            "WHERE g.country = 'Sin país asignado'"
        ),
    }
    timings: dict[str, float | str] = {"status": "ok"}
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            for name, query in queries.items():
                started = time.perf_counter()
                cursor.execute(query)
                cursor.fetchone()
                timings[f"{name}_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return timings


if __name__ == "__main__":
    for result in run_benchmark():
        print(result)
    print({"postgres": benchmark_postgres_indexes()})
