"""Data-structure benchmark (spec 008, research.md R4, task T011). ALL DATA IS SYNTHETIC.

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests \
        python -m tests.benchmark.structure_benchmark [--sizes 10000 100000 1000000]

Three operations, each measured with several implementations that must return the
same result (checked, and reported as "identical"):

  search     the versions of 100 event ids: sequential scan over a list, dict,
             SQL without a key and SQL with the primary key (event_id, updated_s)
  geo        country of each point: naive loop over the Natural Earth polygons
             (as consumer/app/spatial.py does per event) vs Shapely STRtree
  hourly     events per UTC hour: Python loop with a dict vs SQL GROUP BY date_bin

SQL runs in the throw-away schema "bench" (own tables; core and replay are never
touched). The schema is dropped at the end, also on failure. Timing is the median of
N repetitions of the operation after a warm-up (time.perf_counter); the slowest
variants get fewer repetitions (see reps_for). Python memory is the tracemalloc peak
of building the structure plus one run: it does not see GEOS or PostgreSQL memory.
Writes docs/evidence/008/structure-benchmark.md and .json by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import psycopg

from tests.benchmark.api_latency import machine_info
from tests.benchmark.index_benchmark import conninfo, decimal, environment, integer, plan_nodes

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence" / "008"
CATALOG = REPO_ROOT / "frontend" / "public" / "datos" / "paises.geojson"
SCHEMA = "bench"
SIZES = (10_000, 100_000, 1_000_000)
REPEATS = 5
WARMUP = 1
LOOKUPS = 100
SEED = 20250101
YEAR_START = 1_735_689_600  # 2025-01-01T00:00:00Z
YEAR_SECONDS = 365 * 86_400
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass
class Variant:
    key: str
    label: str
    build: Callable[[], Any]
    run: Callable[[Any], Any]
    slow: bool = False        # fewer repetitions from 100 000 rows
    heavy: bool = False       # a single repetition at 1 000 000 rows
    python: bool = True       # memory measurable with tracemalloc
    plan: str | None = None


@dataclass
class Operation:
    key: str
    description: str
    unit: str
    variants: list[Variant] = field(default_factory=list)


def reps_for(variant: Variant, size: int, repeats: int) -> tuple[int, int]:
    """(repetitions, warm-up runs). The slow variants cannot afford 5 runs at 1 000 000 rows."""
    if variant.heavy and size >= 1_000_000:
        return 1, 0
    if (variant.slow or variant.heavy) and size >= 100_000:
        return min(repeats, 3), WARMUP
    return repeats, WARMUP


def digest(result: Any) -> str:
    return hashlib.sha256(repr(result).encode("utf-8")).hexdigest()[:16]


def timed(variant: Variant, size: int, repeats: int) -> dict:
    reps, warmup = reps_for(variant, size, repeats)
    started = time.perf_counter()
    state = variant.build()
    build_ms = (time.perf_counter() - started) * 1000.0
    for _ in range(warmup):
        variant.run(state)
    runs: list[float] = []
    result: Any = None
    for _ in range(reps):
        started = time.perf_counter()
        result = variant.run(state)
        runs.append((time.perf_counter() - started) * 1000.0)
    peak_kib: float | None = None
    if variant.python and not (variant.heavy and size >= 1_000_000):
        del state
        tracemalloc.start()
        try:
            variant.run(variant.build())
            peak_kib = tracemalloc.get_traced_memory()[1] / 1024.0
        finally:
            tracemalloc.stop()
    return {
        "variant": variant.key,
        "label": variant.label,
        "median_ms": statistics.median(runs),
        "runs_ms": runs,
        "repeats": reps,
        "warmup": warmup,
        "build_ms": build_ms,
        "peak_python_kib": peak_kib,
        "plan": variant.plan,
        "digest": digest(result),
        "_result": result,
    }


# --- operation (a): versions by event id ---------------------------------------------


def make_versions(size: int, rng: random.Random) -> list[tuple[str, int, float]]:
    """(event_id, updated_s, magnitude) in update order; 5 % of the events have an older version first."""
    rows: list[tuple[str, int, float]] = []
    for i in range(size):
        updated = YEAR_START + 300 + i * 30
        if i % 20 == 0:
            rows.append((f"ev{i}", updated - 240, round(1 + rng.random() * 6, 2)))
        rows.append((f"ev{i}", updated, round(1 + rng.random() * 6, 2)))
    return rows


def copy_rows(conn: psycopg.Connection, statement: str, rows: Any) -> None:
    with conn.cursor() as cursor, cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def top_plan(conn: psycopg.Connection, sql: str, params: tuple) -> str:
    (plan_json,) = conn.execute("EXPLAIN (FORMAT JSON) " + sql, params).fetchone()
    plan = plan_json[0] if isinstance(plan_json, list) else json.loads(plan_json)[0]
    return " → ".join(dict.fromkeys(plan_nodes(plan["Plan"])))


def search_operation(conn: psycopg.Connection, size: int, lookups: int) -> Operation:
    rng = random.Random(SEED + size)
    rows = make_versions(size, rng)
    ids = [f"ev{i}" for i in rng.sample(range(size), min(lookups, size))] + ["missing"]
    conn.execute(f"TRUNCATE {SCHEMA}.versions_nopk, {SCHEMA}.versions_pk")
    copy_rows(conn, f"COPY {SCHEMA}.versions_nopk (event_id, updated_s, magnitude) FROM STDIN", rows)
    conn.execute(f"INSERT INTO {SCHEMA}.versions_pk SELECT * FROM {SCHEMA}.versions_nopk")
    conn.execute(f"ANALYZE {SCHEMA}.versions_nopk")
    conn.execute(f"ANALYZE {SCHEMA}.versions_pk")

    def build_dict() -> dict[str, list[float]]:
        index: dict[str, list[float]] = {}
        for event_id, _updated, magnitude in rows:
            index.setdefault(event_id, []).append(magnitude)
        return index

    def run_list(data: list) -> tuple:
        return tuple(tuple(m for (eid, _u, m) in data if eid == wanted) for wanted in ids)

    def run_dict(index: dict) -> tuple:
        return tuple(tuple(index.get(wanted, ())) for wanted in ids)

    def sql_runner(table: str) -> Callable[[Any], tuple]:
        statement = f"SELECT magnitude FROM {SCHEMA}.{table} WHERE event_id = %s ORDER BY updated_s"

        def run(_state: Any) -> tuple:
            return tuple(tuple(r[0] for r in conn.execute(statement, (wanted,)).fetchall()) for wanted in ids)

        return run

    def plan_of(table: str) -> str:
        return top_plan(conn, f"SELECT magnitude FROM {SCHEMA}.{table} WHERE event_id = %s ORDER BY updated_s", (ids[0],))

    return Operation(
        "search",
        f"Versiones de {len(ids)} identificadores (uno inexistente) entre {integer(len(rows))} versiones",
        "versiones",
        [
            Variant("list_scan", "lista, búsqueda secuencial", lambda: list(rows), run_list, slow=True),
            Variant("dict", "diccionario por event_id", build_dict, run_dict),
            Variant("sql_no_key", "SQL sin clave primaria", lambda: None, sql_runner("versions_nopk"),
                    slow=True, python=False, plan=plan_of("versions_nopk")),
            Variant("sql_primary_key", "SQL con clave primaria (event_id, updated_s)", lambda: None,
                    sql_runner("versions_pk"), python=False, plan=plan_of("versions_pk")),
        ],
    )


# --- operation (b): point in polygon -----------------------------------------------------


def load_polygons() -> tuple[list[str], list[Any]]:
    """Same catalog and order as consumer/app/spatial.py: sorted by ADM0_A3, first match wins."""
    import geopandas as gpd

    countries = gpd.read_file(CATALOG).to_crs("EPSG:4326").sort_values("ADM0_A3").reset_index(drop=True)
    return [str(code) for code in countries["ADM0_A3"]], list(countries.geometry)


def geo_operation(size: int) -> Operation:
    import numpy as np
    import shapely
    from shapely import STRtree

    ids, polygons = load_polygons()
    rng = np.random.default_rng(SEED + size)
    longitudes = rng.uniform(-180.0, 180.0, size)
    latitudes = rng.uniform(-90.0, 90.0, size)

    def points() -> Any:
        return shapely.points(longitudes, latitudes)

    def run_naive(pts: Any) -> list:
        found: list[str | None] = []
        for point in pts:
            code = None
            for country, polygon in zip(ids, polygons):
                if polygon.intersects(point):
                    code = country
                    break
            found.append(code)
        return found

    def build_tree() -> tuple:
        return STRtree(polygons), points()

    def run_tree(state: tuple) -> list:
        tree, pts = state
        point_idx, polygon_idx = tree.query(pts, predicate="intersects")
        first = np.full(len(pts), len(ids), dtype=np.int64)
        np.minimum.at(first, point_idx, polygon_idx)
        return [ids[i] if i < len(ids) else None for i in first]

    return Operation(
        "geo",
        f"País de {integer(size)} puntos aleatorios entre {len(polygons)} polígonos de Natural Earth",
        "puntos",
        [
            Variant("naive_polygons", "bucle ingenuo sobre todos los polígonos", points, run_naive, heavy=True),
            Variant("strtree", "índice espacial STRtree", build_tree, run_tree),
        ],
    )


# --- operation (c): hourly windows ---------------------------------------------------------


def hourly_operation(conn: psycopg.Connection, size: int) -> Operation:
    rng = random.Random(SEED + size)
    times = [EPOCH + timedelta(seconds=YEAR_START + rng.randrange(YEAR_SECONDS)) for _ in range(size)]
    conn.execute(f"TRUNCATE {SCHEMA}.hour_events")
    copy_rows(conn, f"COPY {SCHEMA}.hour_events (event_time) FROM STDIN", ((t,) for t in times))
    conn.execute(f"ANALYZE {SCHEMA}.hour_events")
    statement = (
        f"SELECT extract(epoch FROM date_bin(interval '1 hour', event_time, timestamptz '2025-01-01 00:00+00'))::bigint, "
        f"count(*) FROM {SCHEMA}.hour_events GROUP BY 1 ORDER BY 1"
    )

    def run_python(_state: Any) -> list:
        counts: dict[datetime, int] = {}
        for moment in times:
            key = moment.replace(minute=0, second=0, microsecond=0)
            counts[key] = counts.get(key, 0) + 1
        return sorted((int(key.timestamp()), count) for key, count in counts.items())

    def run_sql(_state: Any) -> list:
        return [(int(hour), int(count)) for hour, count in conn.execute(statement).fetchall()]

    return Operation(
        "hourly",
        f"Eventos por hora UTC entre {integer(size)} eventos de 2025",
        "eventos",
        [
            Variant("python_dict", "bucle Python con diccionario", lambda: None, run_python),
            Variant("sql_date_bin", "SQL GROUP BY con date_bin", lambda: None, run_sql,
                    python=False, plan=top_plan(conn, statement, ())),
        ],
    )


# --- driver ------------------------------------------------------------------------------


def create_schema(conn: psycopg.Connection) -> None:
    conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    conn.execute(f"CREATE SCHEMA {SCHEMA}")
    conn.execute(f"CREATE TABLE {SCHEMA}.versions_nopk (event_id text NOT NULL, updated_s bigint NOT NULL, magnitude double precision)")
    conn.execute(
        f"CREATE TABLE {SCHEMA}.versions_pk (event_id text NOT NULL, updated_s bigint NOT NULL, "
        f"magnitude double precision, PRIMARY KEY (event_id, updated_s))"
    )
    conn.execute(f"CREATE TABLE {SCHEMA}.hour_events (event_time timestamptz NOT NULL)")


def run_size(conn: psycopg.Connection, size: int, repeats: int, lookups: int) -> list[dict]:
    rows: list[dict] = []
    for build in (
        lambda: search_operation(conn, size, lookups),
        lambda: geo_operation(size),
        lambda: hourly_operation(conn, size),
    ):
        operation = build()
        measured = []
        for variant in operation.variants:
            outcome = timed(variant, size, repeats)
            measured.append(outcome)
            print(
                f"[{size:>9,}] {operation.key:<7} {variant.key:<16} {outcome['median_ms']:12.3f} ms "
                f"({outcome['repeats']} runs)",
                flush=True,
            )
        first = measured[0]["_result"]
        identical = all(item["_result"] == first for item in measured)
        for item in measured:
            del item["_result"]
            rows.append({"operation": operation.key, "description": operation.description, "size": size,
                         "identical": identical, **item})
    return rows


def versions() -> dict[str, str]:
    found = {}
    for package in ("shapely", "geopandas", "numpy", "psycopg"):
        try:
            found[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            found[package] = "?"
    found["python"] = platform.python_version()
    return found


def run_benchmark(sizes: list[int], repeats: int = REPEATS, lookups: int = LOOKUPS) -> dict:
    """Create bench, measure every size, drop bench (also on failure); return the report."""
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        try:
            create_schema(conn)
            results: list[dict] = []
            for size in sizes:
                results.extend(run_size(conn, size, repeats, lookups))
            env = environment(conn)
        finally:
            conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            print(f"schema {SCHEMA} dropped", flush=True)
    env["cpu"] = machine_info()["cpu"]
    return {
        "synthetic": True,
        "environment": env,
        "versions": versions(),
        "parameters": {"sizes": sizes, "repeats": repeats, "warmup": WARMUP, "lookups": lookups, "seed": SEED},
        "results": results,
    }


def markdown(report: dict) -> str:
    env, params = report["environment"], report["parameters"]
    lines = [
        "# Medición de estructuras de datos (spec 008)",
        "",
        "> **SINTÉTICO**: todos los datos de esta medición son generados con semilla fija; no son datos del "
        "observatorio y no se han cargado en `core` ni en `replay`.",
        "",
        f"- Fecha (UTC): {env['date_utc']}",
        f"- Servidor: {env['postgres']}; shared_buffers {env['shared_buffers']}, work_mem {env['work_mem']}",
        f"- Cliente: {env['client']}; CPU {env['cpu']}; {env['cpus']} CPU y {env['memory']} visibles en el contenedor",
    ]
    if env.get("host_note"):
        lines.append(f"- Equipo: {env['host_note']}")
    lines += [
        "- Versiones: " + ", ".join(f"{name} {value}" for name, value in report["versions"].items()),
        "- Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.benchmark.structure_benchmark`",
        "",
        "## Procedimiento",
        "",
        f"1. Se crea el esquema `bench` con tablas propias (no toca `core` ni `replay`) y se elimina al terminar, "
        f"también si la medición falla. Tamaños: {', '.join(integer(s) for s in params['sizes'])}; semilla {params['seed']}.",
        f"2. Tiempo: mediana de {params['repeats']} repeticiones tras {params['warmup']} de calentamiento con "
        "`time.perf_counter`. Las variantes más lentas llevan menos repeticiones: como mucho 3 desde 100.000 filas y "
        "1 (sin calentamiento) el bucle ingenuo de polígonos con 1.000.000 de puntos; la columna «Repeticiones» lo indica.",
        "3. Memoria: pico de `tracemalloc` al construir la estructura y ejecutar la operación una vez; solo ve la memoria "
        "de Python y NumPy, no la de GEOS ni la de PostgreSQL (`—`). No se mide para el bucle ingenuo con 1.000.000 de puntos.",
        f"4. Búsqueda: {params['lookups']} identificadores al azar más uno inexistente sobre versiones "
        "(5 % de los eventos con dos). Las variantes Python miden la búsqueda; la construcción del diccionario se da en «Construcción».",
        "5. Geografía: puntos uniformes en longitud y latitud contra los polígonos de `frontend/public/datos/paises.geojson` "
        "(Natural Earth), con el orden y la regla del consumidor (por `ADM0_A3`, gana el primero que intersecta). "
        "El tiempo del STRtree incluye consultar, no construir el árbol (se da en «Construcción»).",
        "6. Agregación por hora UTC: 2025 con eventos a segundos aleatorios; Python recorre `datetime` con diccionario; "
        "SQL usa `date_bin('1 hour', ...)`. En SQL el tiempo incluye traer el resultado.",
        "7. Todas las variantes de una operación deben devolver el mismo resultado; la columna «Idéntico» lo comprueba.",
        "",
    ]
    for key in dict.fromkeys(row["operation"] for row in report["results"]):
        rows = [r for r in report["results"] if r["operation"] == key]
        lines += [f"## `{key}`", ""]
        for size in dict.fromkeys(r["size"] for r in rows):
            sized = [r for r in rows if r["size"] == size]
            lines += [
                f"### {integer(size)} filas: {sized[0]['description']}",
                "",
                "| Variante | Mediana (ms) | Repeticiones | Construcción (ms) | Pico Python (KiB) | Idéntico | Plan |",
                "|---|---:|---:|---:|---:|:--:|---|",
            ]
            for r in sized:
                memory = integer(round(r["peak_python_kib"])) if r["peak_python_kib"] is not None else "—"
                lines.append(
                    f"| {r['label']} | {decimal(r['median_ms'], 3)} | {r['repeats']} | {decimal(r['build_ms'], 1)} | "
                    f"{memory} | {'sí' if r['identical'] else 'NO'} | {r['plan'] or '—'} |"
                )
            lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=list(SIZES))
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--lookups", type=int, default=LOOKUPS)
    parser.add_argument("--output", type=Path, default=EVIDENCE_DIR / "structure-benchmark.md")
    args = parser.parse_args(argv)
    report = run_benchmark(args.sizes, args.repeats, args.lookups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown(report), encoding="utf-8", newline="\n")
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"written {args.output} and {args.output.with_suffix('.json').name}")
    return 0 if all(row["identical"] for row in report["results"]) else 1


if __name__ == "__main__":
    sys.exit(main())
