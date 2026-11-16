"""Profile of what USGS actually returned (spec 003, FR-036a, research R14, quickstart V10).

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.analysis.source_profile

Reads the stored originals (feed bodies in core.raw_payload, catalog files
under data/usgs/catalog/) and core.extraction, and writes
docs/evidence/003/source-profile.md: per field, observed types, share of
nulls and range; event and geometry types; how often the feed really changes;
request outcomes; request latency; and publication delay of the events.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.conninfo import make_conninfo

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = REPO_ROOT / "data" / "usgs" / "catalog"
OUTPUT = REPO_ROOT / "docs" / "evidence" / "003" / "source-profile.md"

# Fields the pipeline uses, with their unit and meaning (enunciado §4.1).
USED = {
    "id": ("texto", "identificador del evento en USGS"),
    "properties.time": ("ms Unix (UTC)", "momento de ocurrencia"),
    "properties.updated": ("ms Unix (UTC)", "última actualización en USGS; identidad de la versión"),
    "properties.mag": ("adimensional", "magnitud; su escala depende de magType"),
    "properties.magType": ("texto", "tipo de magnitud (ml, mb, mw, md…)"),
    "properties.type": ("texto", "tipo de evento; solo earthquake se publica"),
    "properties.place": ("texto", "descripción libre del lugar"),
    "geometry.type": ("texto", "debe ser Point"),
    "geometry.longitude": ("grados WGS84", "coordinates[0], en [−180, 180]"),
    "geometry.latitude": ("grados WGS84", "coordinates[1], en [−90, 90]"),
    "geometry.depth": ("km", "coordinates[2]; negativa sobre el nivel del mar"),
}


@dataclass
class FieldStats:
    present: int = 0
    nulls: int = 0
    types: Counter = field(default_factory=Counter)
    minimum: Any = None
    maximum: Any = None

    def add(self, value: Any) -> None:
        self.present += 1
        if value is None:
            self.nulls += 1
            self.types["null"] += 1
            return
        kind = type(value).__name__
        self.types[{"str": "texto", "int": "entero", "float": "decimal", "bool": "booleano",
                    "list": "lista", "dict": "objeto"}.get(kind, kind)] += 1
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            self.minimum = value if self.minimum is None else min(self.minimum, value)
            self.maximum = value if self.maximum is None else max(self.maximum, value)
        elif isinstance(value, str):
            length = len(value)
            self.minimum = length if self.minimum is None else min(self.minimum, length)
            self.maximum = length if self.maximum is None else max(self.maximum, length)


@dataclass
class Profile:
    label: str
    responses: int = 0
    features: int = 0
    fields: dict[str, FieldStats] = field(default_factory=lambda: defaultdict(FieldStats))
    event_types: Counter = field(default_factory=Counter)
    geometry_types: Counter = field(default_factory=Counter)
    coordinate_lengths: Counter = field(default_factory=Counter)
    delays_minutes: list[float] = field(default_factory=list)   # updated − time
    first_time: int | None = None
    last_time: int | None = None

    def add_collection(self, payload: dict[str, Any]) -> None:
        self.responses += 1
        for item in payload.get("features", []):
            self.add_feature(item)

    def add_feature(self, item: Any) -> None:
        if not isinstance(item, dict):
            return
        self.features += 1
        self.fields["id"].add(item.get("id"))
        properties = item.get("properties") if isinstance(item.get("properties"), dict) else {}
        for key, value in properties.items():
            self.fields[f"properties.{key}"].add(value)
        geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) else {}
        self.fields["geometry.type"].add(geometry.get("type"))
        self.geometry_types[geometry.get("type")] += 1
        coordinates = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
        self.coordinate_lengths[len(coordinates)] += 1
        for index, name in enumerate(("longitude", "latitude", "depth")):
            self.fields[f"geometry.{name}"].add(coordinates[index] if index < len(coordinates) else None)
        self.event_types[properties.get("type")] += 1
        time, updated = properties.get("time"), properties.get("updated")
        if isinstance(time, (int, float)):
            self.first_time = time if self.first_time is None else min(self.first_time, time)
            self.last_time = time if self.last_time is None else max(self.last_time, time)
            if isinstance(updated, (int, float)):
                self.delays_minutes.append((updated - time) / 60_000)


def conninfo() -> str:
    return make_conninfo(host=os.environ["PGHOST"], port=os.environ.get("PGPORT", "5432"), user=os.environ["PGUSER"],
                         password=os.environ["PGPASSWORD"], dbname=os.environ["POSTGRES_DB"])


def feed_profile(conn: psycopg.Connection) -> Profile:
    """Every distinct feed body still stored (one per content fingerprint)."""
    profile = Profile("Feed all_day.geojson (originales distintos guardados)")
    rows = conn.execute(
        "SELECT DISTINCT r.body FROM core.raw_payload r JOIN core.extraction e ON e.content_sha256 = r.content_sha256 "
        "WHERE r.encoding = 'gzip' AND e.source = 'usgs_feed' AND e.outcome = 'ok'"
    ).fetchall()
    for (body,) in rows:
        profile.add_collection(json.loads(gzip.decompress(body)))
    return profile


def catalog_profile(directory: Path) -> Profile:
    profile = Profile("Catálogo FDSN (ficheros de data/usgs/catalog)")
    for path in sorted(directory.glob("*.geojson")):
        profile.add_collection(json.loads(path.read_bytes()))
    return profile


def percentile(values: list[float], share: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(share * (len(ordered) - 1))))]


def number(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}".replace(",", ".")
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def field_table(profile: Profile) -> list[str]:
    lines = ["| Campo | Usado | Unidad | Tipos observados | Presente | Nulos | Mín. | Máx. |",
             "|---|---|---|---|---:|---:|---:|---:|"]
    for name in sorted(profile.fields, key=lambda key: (key not in USED, key)):
        stats = profile.fields[name]
        unit = USED.get(name, ("", ""))[0]
        types = ", ".join(f"{kind} {count}" for kind, count in stats.types.most_common())
        share = f"{100 * stats.nulls / profile.features:.1f} %".replace(".", ",") if profile.features else "—"
        bounds = (number(stats.minimum, 2), number(stats.maximum, 2))
        if name in ("properties.time", "properties.updated") and stats.minimum is not None:
            bounds = tuple(datetime.fromtimestamp(v / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                           for v in (stats.minimum, stats.maximum))
        if "texto" in stats.types and name not in ("geometry.type",):
            bounds = (f"long. {bounds[0]}", f"long. {bounds[1]}")
        lines.append(f"| `{name}` | {'sí' if name in USED else ''} | {unit} | {types} | {number(stats.present)} | "
                     f"{share} | {bounds[0]} | {bounds[1]} |")
    return lines


def summary_lines(profile: Profile) -> list[str]:
    def when(ms: int | None) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if ms else "—"

    delays = profile.delays_minutes
    return [
        f"- Respuestas analizadas: {number(profile.responses)}; elementos: {number(profile.features)}",
        f"- Ocurrencias entre {when(profile.first_time)} y {when(profile.last_time)} UTC",
        f"- Tipos de evento: " + ", ".join(f"`{kind}` {number(n)}" for kind, n in profile.event_types.most_common()),
        f"- Geometrías: " + ", ".join(f"`{kind}` {number(n)}" for kind, n in profile.geometry_types.most_common())
        + "; coordenadas por punto: " + ", ".join(f"{k}: {number(n)}" for k, n in sorted(profile.coordinate_lengths.items())),
        f"- `updated − time` (minutos): mediana {number(statistics.median(delays) if delays else None)}, "
        f"percentil 95 {number(percentile(delays, 0.95))}, máximo {number(max(delays) if delays else None)}",
    ]


def query_rows(conn: psycopg.Connection, sql: str) -> list[tuple]:
    return conn.execute(sql).fetchall()


def requests_section(conn: psycopg.Connection) -> list[str]:
    lines = ["## Consultas registradas", "", "| Fuente | Propósito | Resultado | Consultas | Primera | Última |",
             "|---|---|---|---:|---|---|"]
    for source, purpose, outcome, n, first, last in query_rows(conn, """
        SELECT source, purpose, outcome, count(*), min(requested_at), max(requested_at)
        FROM core.extraction GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""):
        lines.append(f"| `{source}` | `{purpose}` | `{outcome}` | {number(n)} | {first:%Y-%m-%d %H:%M} | {last:%Y-%m-%d %H:%M} |")

    lines += ["", "### Latencia de las consultas (`duration_ms`, reintentos incluidos)", "",
              "| Fuente | Tipo | Consultas | Mediana (ms) | Percentil 95 (ms) | Máximo (ms) |", "|---|---|---:|---:|---:|---:|"]
    for source, endpoint, n, median, p95, maximum in query_rows(conn, """
        SELECT source, coalesce(request_params ->> 'endpoint', 'feed'), count(*),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_ms),
               percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms), max(duration_ms)
        FROM core.extraction WHERE duration_ms IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2"""):
        lines.append(f"| `{source}` | {endpoint} | {number(n)} | {number(median, 0)} | {number(p95, 0)} | {number(maximum)} |")

    lines += ["", "### Frecuencia real de cambio del feed", ""]
    (hours, requests, distinct), = query_rows(conn, """
        SELECT count(DISTINCT date_trunc('hour', requested_at)), count(*), count(DISTINCT content_sha256)
        FROM core.extraction WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')""")
    per_hour = query_rows(conn, """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY n), min(n), max(n) FROM (
          SELECT date_trunc('hour', requested_at) h, count(DISTINCT content_sha256) n
          FROM core.extraction WHERE source = 'usgs_feed' AND outcome = 'ok' GROUP BY 1) s""")[0]
    not_modified = query_rows(conn, "SELECT count(*) FROM core.extraction WHERE source = 'usgs_feed' AND outcome = 'not_modified'")[0][0]
    lines += [f"- {number(requests)} consultas correctas en {number(hours)} horas distintas; {number(distinct)} contenidos distintos "
              f"(huella de la lista de eventos).",
              f"- Contenidos distintos por hora: mediana {number(per_hour[0], 0)}, mínimo {number(per_hour[1])}, máximo {number(per_hour[2])}.",
              f"- Respuestas «sin cambios» (304): {number(not_modified)}."]

    lines += ["", "### Retraso de ingesta de los eventos del feed (`first_ingested_at − event_time`)", ""]
    delay = query_rows(conn, """
        SELECT count(*), percentile_cont(0.5) WITHIN GROUP (ORDER BY d), percentile_cont(0.95) WITHIN GROUP (ORDER BY d)
        FROM (SELECT extract(epoch FROM c.first_ingested_at - c.event_time) / 60 AS d FROM core.event_current c
              WHERE c.source = 'usgs_feed'
                AND EXISTS (SELECT 1 FROM core.extraction e
                            WHERE e.source = 'usgs_feed' AND e.outcome IN ('ok', 'not_modified')
                              AND e.requested_at BETWEEN c.event_time - interval '2 minutes' AND c.event_time)) s""")[0]
    lines.append(f"- {number(delay[0])} eventos ocurridos con el productor funcionando (hubo una consulta correcta en los "
                 f"2 minutos anteriores); mediana {number(delay[1])} min; percentil 95 {number(delay[2])} min. Incluye "
                 "el retraso con que USGS publica el evento, el minuto entre consultas y el paso por Kafka y el "
                 "consumidor. Se excluyen los eventos que ya estaban en la ventana de 24 h al arrancar y los ocurridos "
                 "durante una parada: su retraso mide la parada, no la ingesta.")

    errors = query_rows(conn, """
        SELECT source, outcome, http_status, left(error_detail, 120), count(*) FROM core.extraction
        WHERE outcome NOT IN ('ok', 'not_modified') GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC LIMIT 10""")
    lines += ["", "### Errores registrados", ""]
    if errors:
        lines += ["| Fuente | Resultado | HTTP | Detalle | Veces |", "|---|---|---:|---|---:|"]
        lines += [f"| `{s}` | `{o}` | {h or '—'} | {d or ''} | {number(n)} |" for s, o, h, d, n in errors]
    else:
        lines.append("Ninguno en el periodo observado.")
    return lines


def write_profile(output: Path, profiles: Iterable[Profile], conn: psycopg.Connection) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Perfil de la fuente: respuestas reales de USGS (V10)",
        "",
        f"- Generado (UTC): {now}",
        "- Orden: `docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.analysis.source_profile`",
        "- Datos: originales guardados en `core.raw_payload` (feed, un cuerpo por contenido distinto mientras dure su "
        "retención) y ficheros del catálogo en `data/usgs/catalog/`; consultas de `core.extraction`.",
        "- «Usado» marca los campos que lee el sistema (enunciado §4.1). «Nulos» incluye valores `null` y campos ausentes en "
        "coordenadas; las longitudes de texto se dan en caracteres.",
        "",
    ]
    for profile in profiles:
        lines += [f"## {profile.label}", ""] + summary_lines(profile) + [""] + field_table(profile) + [""]
    lines += requests_section(conn)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog-dir", type=Path, default=CATALOG_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    with psycopg.connect(conninfo()) as conn:
        profiles = [feed_profile(conn), catalog_profile(args.catalog_dir)]
        write_profile(args.output, profiles, conn)
    print(f"written {args.output}: " + "; ".join(f"{p.label}: {p.responses} responses, {p.features} features" for p in profiles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
