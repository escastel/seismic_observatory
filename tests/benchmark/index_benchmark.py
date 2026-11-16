"""Index benchmark of the event model (FR-027, research.md R11, quickstart V11).

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests \
        python -m tests.benchmark.index_benchmark

Creates the schema "bench" from the same template as core and replay
(db/sql/040_event_tables.sql), fills it with 10 000, 100 000 and 1 000 000
synthetic events, and measures five API queries plus last_ingestion without
and with each candidate secondary index. Each measurement is the median of
5 runs of EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) after one warm-up run.
Writes docs/evidence/002/index-benchmark.md and .json and drops "bench" at
the end, also on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "db" / "sql" / "040_event_tables.sql"
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence" / "002"
SCHEMA = "bench"
SIZES = (10_000, 100_000, 1_000_000)
RUNS = 5
KEEP_RATIO = 2.0  # an index stays if its query is at least this many times faster at the largest size


@dataclass(frozen=True)
class Query:
    key: str
    description: str
    sql: str


@dataclass(frozen=True)
class Candidate:
    key: str
    ddl: str
    name: str
    queries: tuple[str, ...]
    decision_rule: str = "keep_if_faster"  # or "measure_only"


QUERIES = (
    Query(
        "last_24h",
        "Eventos de las últimas 24 h (mapa por defecto)",
        "SELECT event_id, event_time, magnitude, longitude, latitude FROM bench.event_current "
        "WHERE event_time >= timestamptz '2025-12-31 00:00+00' AND event_time < timestamptz '2026-01-01 00:00+00' "
        "ORDER BY event_time DESC",
    ),
    Query(
        "month_by_hour",
        "Un mes agrupado por hora UTC (serie temporal)",
        "SELECT date_trunc('hour', event_time AT TIME ZONE 'UTC') AS hour, count(*) FROM bench.event_current "
        "WHERE event_time >= timestamptz '2025-06-01 00:00+00' AND event_time < timestamptz '2025-07-01 00:00+00' "
        "GROUP BY 1 ORDER BY 1",
    ),
    Query(
        "country_interval",
        "Un país en un mes (filtro por país)",
        "SELECT event_id, event_time, magnitude FROM bench.event_current "
        "WHERE country_id = 'JPN' AND event_time >= timestamptz '2025-03-01 00:00+00' "
        "AND event_time < timestamptz '2025-04-01 00:00+00' ORDER BY event_time DESC",
    ),
    Query(
        "min_magnitude_year",
        "Magnitud mínima 4 sobre el año completo",
        "SELECT event_id, event_time, magnitude FROM bench.event_current "
        "WHERE magnitude >= 4 AND event_time >= timestamptz '2025-01-01 00:00+00' "
        "AND event_time < timestamptz '2026-01-01 00:00+00' ORDER BY event_time DESC",
    ),
    Query(
        "versions_of_event",
        "Versiones de un event_id (historial)",
        "SELECT updated_at, magnitude, payload FROM {versions} WHERE event_id = %(event_id)s ORDER BY updated_at",
    ),
    Query(
        "last_ingestion",
        "Última consulta correcta al feed (last_ingestion)",
        "SELECT max(requested_at) FROM bench.extraction "
        "WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')",
    ),
)

CANDIDATES = (
    Candidate(
        "event_time",
        "CREATE INDEX ix_bench_event_time ON bench.event_current (event_time)",
        "ix_bench_event_time",
        ("last_24h", "month_by_hour"),
    ),
    Candidate(
        "country_event_time",
        "CREATE INDEX ix_bench_country_event_time ON bench.event_current (country_id, event_time)",
        "ix_bench_country_event_time",
        ("country_interval",),
    ),
    Candidate(
        "magnitude_event_time",
        "CREATE INDEX ix_bench_magnitude_event_time ON bench.event_current (magnitude, event_time)",
        "ix_bench_magnitude_event_time",
        ("min_magnitude_year",),
    ),
    Candidate(
        "brin_event_time",
        "CREATE INDEX ix_bench_brin_event_time ON bench.event_current USING brin (event_time)",
        "ix_bench_brin_event_time",
        ("last_24h", "month_by_hour"),
        "measure_only",
    ),
    Candidate(
        "extraction_last_ok",
        "CREATE INDEX ix_bench_extraction_last_ok ON bench.extraction (requested_at) "
        "WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')",
        "ix_bench_extraction_last_ok",
        ("last_ingestion",),
    ),
)


@dataclass
class Measurement:
    size: int
    query: str
    index: str | None          # None = only primary keys
    median_ms: float
    runs_ms: list[float]
    shared_buffers: int        # shared hit + read of the top plan node, median run
    plan_nodes: list[str] = field(default_factory=list)
    index_bytes: int | None = None


def conninfo() -> str:
    def env(name: str, default: str | None = None) -> str:
        value = os.environ.get(name, default)
        if not value:
            raise SystemExit(f"Environment variable {name} is required")
        return value

    return make_conninfo(
        host=env("PGHOST"),
        port=env("PGPORT", "5432"),
        user=env("PGUSER"),
        password=env("PGPASSWORD"),
        dbname=os.environ.get("BENCH_DATABASE") or env("POSTGRES_DB"),
    )


def create_schema(conn: psycopg.Connection) -> None:
    conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    conn.execute(f"CREATE SCHEMA {SCHEMA}")
    env = {**os.environ, "PGDATABASE": conn.info.dbname}
    subprocess.run(
        ["psql", "--no-psqlrc", "--quiet", "--set", "ON_ERROR_STOP=1", "--set", f"schema={SCHEMA}", "--file", str(TEMPLATE)],
        check=True,
        env=env,
    )
    # A copy of event_version without primary key, to measure what the key gives
    # to the versions-of-an-event query; and a copy of core.extraction.
    conn.execute(
        f"CREATE TABLE {SCHEMA}.extraction (LIKE core.extraction INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"
    )
    conn.execute(f"ALTER TABLE {SCHEMA}.extraction ADD PRIMARY KEY (extraction_id)")


def load(conn: psycopg.Connection, size: int) -> str:
    """Fill bench with `size` events; returns an event_id that has two versions."""
    conn.execute(f"DROP TABLE IF EXISTS {SCHEMA}.event_version_nopk")
    conn.execute(f"TRUNCATE {SCHEMA}.event_version, {SCHEMA}.event_current, {SCHEMA}.extraction")
    # Events uniform over 2025 and inserted in time order, as the live feed does.
    # Magnitudes follow Gutenberg-Richter with b = 1 from M1, capped at M8:
    # each unit of magnitude is ten times rarer than the previous one.
    # 30 % of the events have no country (sea).
    conn.execute(
        f"""
        INSERT INTO {SCHEMA}.event_current
            (event_id, source, event_time, updated_at, magnitude, mag_type,
             longitude, latitude, depth_km, place, country_id)
        SELECT 'bench' || g,
               'usgs_feed',
               t,
               t + interval '10 minutes',
               round(least(8.0, 1.0 - log(1.0 - random()))::numeric, 2)::double precision,
               'ml',
               -180 + random() * 360,
               -90 + random() * 180,
               round((random() ^ 3 * 700)::numeric, 2)::double precision,
               NULL,
               CASE WHEN random() < 0.3 THEN NULL
                    ELSE countries[1 + floor(random() * cardinality(countries))::int] END
        FROM generate_series(1, %(size)s) AS g,
             LATERAL (SELECT timestamptz '2025-01-01 00:00+00'
                             + (g - 1) * (interval '365 days' / %(size)s) AS t) AS times,
             (SELECT array_agg(country_id ORDER BY country_id) AS countries FROM core.dim_country) AS c
        """,
        {"size": size},
    )
    # One version per event (the current one) plus an earlier one for 5 %.
    conn.execute(
        f"""
        INSERT INTO {SCHEMA}.event_version
            (event_id, updated_at, source, event_time, magnitude, mag_type, depth_km,
             longitude, latitude, payload, kafka_topic, kafka_partition, kafka_offset)
        SELECT e.event_id, v.updated_at, e.source, e.event_time, e.magnitude, e.mag_type, e.depth_km,
               e.longitude, e.latitude,
               jsonb_build_object('type', 'Feature', 'id', e.event_id,
                                  'properties', jsonb_build_object('mag', e.magnitude, 'time', e.event_time,
                                                                   'updated', v.updated_at, 'type', 'earthquake'),
                                  'geometry', jsonb_build_object('type', 'Point',
                                      'coordinates', jsonb_build_array(e.longitude, e.latitude, e.depth_km))),
               'earthquakes.live', 0, row_number() OVER (ORDER BY e.event_time, v.updated_at)
        FROM {SCHEMA}.event_current e
        CROSS JOIN LATERAL (
            SELECT e.updated_at AS updated_at
            UNION ALL
            SELECT e.updated_at - interval '4 minutes' WHERE substr(e.event_id, 6)::int % 20 = 0
        ) AS v
        """
    )
    conn.execute(f"CREATE TABLE {SCHEMA}.event_version_nopk AS SELECT * FROM {SCHEMA}.event_version")
    # One feed request a minute; 5 % catalog requests, 3 % failed outcomes.
    conn.execute(
        f"""
        INSERT INTO {SCHEMA}.extraction
            (extraction_id, source, purpose, request_url, requested_at, outcome, attempt_count)
        SELECT g,
               CASE WHEN g %% 20 = 0 THEN 'usgs_catalog' ELSE 'usgs_feed' END,
               CASE WHEN g %% 20 = 0 THEN 'gap_recovery' ELSE 'live' END,
               'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson',
               timestamptz '2025-01-01 00:00+00' + g * interval '1 minute',
               CASE WHEN g %% 33 = 0 THEN 'timeout' WHEN g %% 7 = 0 THEN 'not_modified' ELSE 'ok' END,
               1
        FROM generate_series(1, %(size)s) AS g
        """,
        {"size": size},
    )
    conn.execute(f"VACUUM (ANALYZE) {SCHEMA}.event_current")
    conn.execute(f"VACUUM (ANALYZE) {SCHEMA}.event_version")
    conn.execute(f"VACUUM (ANALYZE) {SCHEMA}.event_version_nopk")
    conn.execute(f"VACUUM (ANALYZE) {SCHEMA}.extraction")
    middle = (size // 2) // 20 * 20 or 20
    return f"bench{middle}"


def plan_nodes(node: dict) -> list[str]:
    label = node["Node Type"] + (f" using {node['Index Name']}" if "Index Name" in node else "")
    nodes = [label]
    for child in node.get("Plans", []):
        nodes.extend(plan_nodes(child))
    return nodes


def measure(conn: psycopg.Connection, sql: str, params: dict) -> tuple[float, list[float], int, list[str]]:
    explain = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
    conn.execute(explain, params)  # warm-up
    runs: list[tuple[float, int, list[str]]] = []
    for _ in range(RUNS):
        (plan_json,) = conn.execute(explain, params).fetchone()
        result = plan_json[0] if isinstance(plan_json, list) else json.loads(plan_json)[0]
        top = result["Plan"]
        buffers = int(top.get("Shared Hit Blocks", 0)) + int(top.get("Shared Read Blocks", 0))
        runs.append((float(result["Execution Time"]), buffers, plan_nodes(top)))
    times = [run[0] for run in runs]
    median = statistics.median(times)
    closest = min(runs, key=lambda run: abs(run[0] - median))
    return median, times, closest[1], closest[2]


def run_size(conn: psycopg.Connection, size: int) -> list[Measurement]:
    started = time.monotonic()
    event_id = load(conn, size)
    print(f"[{size:>9,}] loaded in {time.monotonic() - started:.1f} s; versions measured for {event_id}", flush=True)
    results: list[Measurement] = []

    def record(query: Query, index: str | None, versions_table: str, index_bytes: int | None = None) -> None:
        sql = query.sql.format(versions=versions_table)
        median, times, buffers, nodes = measure(conn, sql, {"event_id": event_id})
        results.append(Measurement(size, query.key, index, median, times, buffers, nodes, index_bytes))
        print(f"[{size:>9,}] {query.key:<20} {index or 'only primary keys':<28} {median:10.3f} ms  {buffers:>8} buffers", flush=True)

    for query in QUERIES:
        if query.key == "versions_of_event":
            # The index under test is the primary key itself: compare with a copy without it.
            record(query, None, f"{SCHEMA}.event_version_nopk")
            pk_bytes = conn.execute(
                f"SELECT pg_relation_size('{SCHEMA}.event_version_pkey')"
            ).fetchone()[0]
            record(query, "event_version_pkey", f"{SCHEMA}.event_version", pk_bytes)
            continue
        record(query, None, f"{SCHEMA}.event_version")

    for candidate in CANDIDATES:
        conn.execute(candidate.ddl)
        table = "extraction" if candidate.key == "extraction_last_ok" else "event_current"
        conn.execute(f"ANALYZE {SCHEMA}.{table}")
        index_bytes = conn.execute(f"SELECT pg_relation_size('{SCHEMA}.{candidate.name}')").fetchone()[0]
        for query in QUERIES:
            if query.key in candidate.queries:
                record(query, candidate.key, f"{SCHEMA}.event_version", index_bytes)
        conn.execute(f"DROP INDEX {SCHEMA}.{candidate.name}")
    return results


def environment(conn: psycopg.Connection) -> dict[str, str]:
    def setting(name: str) -> str:
        return conn.execute(f"SHOW {name}").fetchone()[0]

    memory = "?"
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                memory = f"{int(line.split()[1]) / 1_048_576:.1f} GiB"
    except OSError:
        pass
    return {
        "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "postgres": conn.execute("SELECT version()").fetchone()[0],
        "shared_buffers": setting("shared_buffers"),
        "work_mem": setting("work_mem"),
        "client": f"{platform.system()} {platform.release()} {platform.machine()}, Python {platform.python_version()}",
        "cpus": str(os.cpu_count()),
        "memory": memory,
        "host_note": os.environ.get("BENCH_HOST_NOTE", ""),
    }


def decisions(results: list[Measurement]) -> list[dict]:
    largest = max(m.size for m in results)
    by_key = {(m.size, m.query, m.index): m for m in results}
    rows = []
    for candidate in CANDIDATES:
        ratios = {}
        for query in candidate.queries:
            base = by_key[(largest, query, None)]
            with_index = by_key[(largest, query, candidate.key)]
            ratios[query] = base.median_ms / with_index.median_ms if with_index.median_ms else float("inf")
        best = max(ratios.values())
        if candidate.decision_rule == "measure_only":
            verdict = "medido (alternativa a event_time)"
        else:
            verdict = "conservar" if best >= KEEP_RATIO else "descartar"
        rows.append({"index": candidate.key, "ddl": candidate.ddl, "ratios": ratios, "best_ratio": best, "verdict": verdict})
    base = by_key[(largest, "versions_of_event", None)]
    pk = by_key[(largest, "versions_of_event", "event_version_pkey")]
    rows.append(
        {
            "index": "event_version_pkey",
            "ddl": "PRIMARY KEY (event_id, updated_at)",
            "ratios": {"versions_of_event": base.median_ms / pk.median_ms},
            "best_ratio": base.median_ms / pk.median_ms,
            "verdict": "obligatorio (clave primaria)",
        }
    )
    return rows


def integer(value: int) -> str:
    """Spanish thousands separator: 1.000.000."""
    return f"{value:,}".replace(",", ".")


def decimal(value: float, digits: int) -> str:
    """Spanish decimal comma: 12,345."""
    return f"{value:.{digits}f}".replace(".", ",")


def markdown(env: dict[str, str], results: list[Measurement], verdicts: list[dict]) -> str:
    descriptions = {query.key: query.description for query in QUERIES}
    lines = [
        "# Medición de índices del modelo (V11)",
        "",
        f"- Fecha (UTC): {env['date_utc']}",
        f"- Servidor: {env['postgres']}; shared_buffers {env['shared_buffers']}, work_mem {env['work_mem']}",
        f"- Cliente: {env['client']}; {env['cpus']} CPU y {env['memory']} visibles en el contenedor",
    ]
    if env["host_note"]:
        lines.append(f"- Equipo: {env['host_note']}")
    lines += [
        "- Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.benchmark.index_benchmark`",
        "",
        "## Procedimiento",
        "",
        "1. Se crea el esquema `bench` con la misma plantilla que `core` y `replay` "
        "(`db/sql/040_event_tables.sql`), más una copia de `core.extraction`.",
        "2. Para cada tamaño (10.000, 100.000 y 1.000.000 de eventos) se cargan datos sintéticos: "
        "eventos repartidos de forma uniforme en 2025 e insertados en orden temporal; magnitudes de "
        "Gutenberg-Richter con b = 1 desde M1 y tope en M8 (cada unidad, diez veces menos eventos; "
        "≈0,1 % con M ≥ 4); un 30 % sin país y el resto repartido entre los 177 países; una versión "
        "por evento y una segunda para el 5 %; una extracción por minuto, con un 5 % del catálogo y un "
        "3 % fallidas. Después, `VACUUM (ANALYZE)`.",
        "3. Cada consulta se ejecuta con `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`: una ejecución de "
        f"calentamiento y {RUNS} medidas. Se anota la mediana del tiempo de ejecución y los búferes "
        "compartidos (leídos más en caché) del nodo superior de la ejecución mediana.",
        "4. Primero sin índices secundarios (solo claves primarias); después se crea cada candidato, se "
        "analiza la tabla, se mide y se elimina. Para las versiones de un evento, cuyo índice es la "
        "propia clave primaria, se compara contra una copia de `event_version` sin clave.",
        f"5. Criterio (research.md R11): se conserva un índice si alguna de sus consultas es al menos "
        f"{KEEP_RATIO:g} veces más rápida en mediana con 1.000.000 de filas. El BRIN solo se mide.",
        "6. El esquema `bench` se elimina al terminar, también si la medición falla.",
        "",
        "## Decisión con 1.000.000 de filas",
        "",
        "| Índice | Consulta | Sin índice / con índice | Decisión |",
        "|---|---|---|---|",
    ]
    for row in verdicts:
        ratios = "; ".join(f"`{query}` ×{decimal(ratio, 1)}" for query, ratio in row["ratios"].items())
        lines.append(f"| `{row['index']}` | {', '.join(f'`{q}`' for q in row['ratios'])} | {ratios} | {row['verdict']} |")
    lines += ["", "## Mediciones", ""]
    for query in QUERIES:
        lines += [
            f"### `{query.key}`: {descriptions[query.key]}",
            "",
            "| Filas | Índice | Mediana (ms) | Búferes | Tamaño del índice | Plan |",
            "|---:|---|---:|---:|---:|---|",
        ]
        for m in (m for m in results if m.query == query.key):
            size = f"{decimal(m.index_bytes / 1_048_576, 2)} MiB" if m.index_bytes is not None else "—"
            name = "sin índice secundario" if m.index is None else f"`{m.index}`"
            if query.key == "versions_of_event" and m.index is None:
                name = "copia sin clave primaria"
            plan = " → ".join(dict.fromkeys(m.plan_nodes))
            lines.append(f"| {integer(m.size)} | {name} | {decimal(m.median_ms, 3)} | {integer(m.shared_buffers)} | {size} | {plan} |")
        lines += ["", f"```sql\n{query.sql.format(versions='bench.event_version')}\n```", ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", type=int, nargs="+", default=list(SIZES))
    parser.add_argument("--output", type=Path, default=EVIDENCE_DIR / "index-benchmark.md")
    args = parser.parse_args(argv)
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        try:
            create_schema(conn)
            results: list[Measurement] = []
            for size in args.sizes:
                results.extend(run_size(conn, size))
            env = environment(conn)
        finally:
            conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            print(f"schema {SCHEMA} dropped", flush=True)

    verdicts = decisions(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown(env, results, verdicts), encoding="utf-8", newline="\n")
    args.output.with_suffix(".json").write_text(
        json.dumps({"environment": env, "results": [asdict(m) for m in results], "decisions": verdicts}, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"written {args.output} and {args.output.with_suffix('.json').name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
