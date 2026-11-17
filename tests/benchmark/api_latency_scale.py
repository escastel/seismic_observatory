"""API latency with synthetic events at scale (spec 008, research.md R5, task T014). SYNTHETIC DATA.

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests \
        python -m tests.benchmark.api_latency_scale [--size 1000000] [--runs 30] [--warmup 5] [--json]

api/ is not modified. The FastAPI app is imported in process (no network, no tunnel),
the schema "bench" is filled from the same template as core and replay (as
index_benchmark does), the reader role of the API gets SELECT on it, and the in-memory
SEARCH_PATHS["replay"] of api/app/db.py is replaced by "bench, core". The replay mode
of the API then reads bench. core and replay are never touched; bench is dropped at the
end, also on failure.

Requests (contracts/api.md of spec 006), after the warm-up, sequentially:
  /api/eventos?mode=replay&limit=10
  /api/eventos?mode=replay&limit=1000
  /api/estadisticas?mode=replay&start=2025-01-01T00:00:00Z&end=2026-01-01T00:00:00Z&min_mag=4
Reports median, p95 and maximum in ms. Exit code 1 if a request fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time

import psycopg

# Defaults needed to import api.app.main; real values from the environment win.
os.environ.setdefault("CORS_ORIGINS", "https://observatorio.netlify.app,http://localhost:4200")

from tests.benchmark.api_latency import machine_info  # noqa: E402
from tests.benchmark.index_benchmark import SCHEMA, conninfo, create_schema, load  # noqa: E402
from tests.support.asgi_client import call_asgi  # noqa: E402

START = "2025-01-01T00:00:00Z"
END = "2026-01-01T00:00:00Z"
INDEX_STATEMENTS = (
    f"CREATE INDEX event_current_event_time_idx ON {SCHEMA}.event_current (event_time)",
    f"CREATE INDEX event_current_country_event_time_idx ON {SCHEMA}.event_current (country_id, event_time)",
    f"CREATE INDEX event_current_magnitude_event_time_idx ON {SCHEMA}.event_current (magnitude, event_time)",
)
CASES = (
    ("events limit=10", "/api/eventos", {"mode": "replay", "limit": 10}),
    ("events limit=1000", "/api/eventos", {"mode": "replay", "limit": 1000}),
    ("events limit=1000 (2025)", "/api/eventos", {"mode": "replay", "limit": 1000, "start": START, "end": END}),
    ("statistics (2025, no filter)", "/api/estadisticas", {"mode": "replay", "start": START, "end": END}),
    (
        "statistics (2025, min_mag=4)",
        "/api/estadisticas",
        {"mode": "replay", "start": START, "end": END, "min_mag": 4},
    ),
)


async def measure(app, path: str, params: dict, runs: int, warmup: int) -> dict:
    timings: list[float] = []
    errors: list[str] = []
    total = None
    for index in range(warmup + runs):
        started = time.perf_counter()
        response = await call_asgi(app, "GET", path, params)
        elapsed = (time.perf_counter() - started) * 1000.0
        if response.status != 200:
            errors.append(f"HTTP {response.status}: {response.text[:200]}")
            continue
        if total is None:
            body = response.json()
            total = body.get("metadata", {}).get("total", body.get("total"))
        if index >= warmup:
            timings.append(elapsed)
    result: dict = {"total_events": total, "errors": errors, "runs_ok": len(timings)}
    if timings:
        ordered = sorted(timings)
        p95_index = min(len(ordered) - 1, max(0, round(0.95 * len(ordered)) - 1))
        result.update(median_ms=statistics.median(ordered), p95_ms=ordered[p95_index], max_ms=ordered[-1])
    return result


async def run_requests(dbname: str, runs: int, warmup: int) -> list[dict]:
    # Imported here: importing api.app.main reads the settings of the environment.
    from api.app import db as api_db
    from api.app.main import app
    from common.settings import DatabaseSettings

    api_db.SEARCH_PATHS["replay"] = f"{SCHEMA}, core"  # in memory only; api/ is untouched
    settings = DatabaseSettings(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        database=dbname,
        user="observatory_reader",
        password=os.environ["DB_READER_PASSWORD"],
    )
    app.state.pools = {mode: None for mode in api_db.MODES}
    await api_db.connect_in_background(app, "replay", settings)  # same pool, size and timeout as the API
    try:
        rows = []
        for name, path, params in CASES:
            rows.append({"name": name, "path": path, "params": params, **await measure(app, path, params, runs, warmup)})
        return rows
    finally:
        await app.state.pools["replay"].close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=int, default=1_000_000, help="synthetic events in bench")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    parser.add_argument(
        "--indexes",
        action="store_true",
        help="create on bench the three secondary indexes of db/sql/060_indexes.sql (the real schemas have them)",
    )
    args = parser.parse_args(argv)

    with psycopg.connect(conninfo(), autocommit=True) as conn:
        try:
            create_schema(conn)
            started = time.monotonic()
            load(conn, args.size)
            print(f"bench loaded with {args.size:,} synthetic events in {time.monotonic() - started:.1f} s", flush=True)
            if args.indexes:
                for statement in INDEX_STATEMENTS:
                    conn.execute(statement)
                conn.execute(f"ANALYZE {SCHEMA}.event_current")
                print("secondary indexes created on bench.event_current", flush=True)
            conn.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO observatory_reader")
            conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO observatory_reader")
            rows = asyncio.run(run_requests(conn.info.dbname, args.runs, args.warmup))
        finally:
            conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            print(f"schema {SCHEMA} dropped", flush=True)

    failed = any(row["errors"] or "median_ms" not in row for row in rows)
    report = {
        "synthetic": True,
        "in_process": True,
        "size": args.size,
        "secondary_indexes": args.indexes,
        "runs": args.runs,
        "warmup": args.warmup,
        "machine": machine_info(),
        "results": rows,
        "passed": not failed,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["passed"] else 1
    indexed = "with" if args.indexes else "without"
    print(f"SYNTHETIC, in process (no network), replay mode reading bench {indexed} secondary indexes; {args.size:,} events")
    print(f"Runs: {args.runs} after {args.warmup} warm-up\n")
    header = f"{'name':<30}{'total':>11}{'median':>10}{'p95':>10}{'max':>10}  (ms)"
    print(header)
    print("-" * len(header))
    for row in rows:
        if "median_ms" in row:
            print(f"{row['name']:<30}{str(row['total_events']):>11}{row['median_ms']:>10.1f}"
                  f"{row['p95_ms']:>10.1f}{row['max_ms']:>10.1f}")
        else:
            print(f"{row['name']:<30}{str(row['total_events']):>11}{'FAILED':>10}")
        for error in row["errors"][:3]:
            print(f"  error: {error}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
