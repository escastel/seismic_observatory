"""Selection of the events to replay (spec 005, research R2, R7, R8).

Pure part: reads GeoJSON FeatureCollection files and filters them by period,
minimum magnitude and bounding box. No database and no network. The features
are returned untouched (constitution, principle VI).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

from .. import provenance
from ..fingerprint import bytes_fingerprint, file_fingerprint
from ..provenance import Counts
from ..usgs import FetchResult

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class Selection:
    start: datetime
    end: datetime
    min_magnitude: float
    bbox: BBox | None
    files: tuple[str, ...]
    features: list[dict[str, Any]] = field(default_factory=list)
    without_magnitude_dropped: int = 0
    content_sha256: str = ""

    @property
    def count(self) -> int:
        return len(self.features)

    @property
    def first_time_ms(self) -> int | None:
        return _time_ms(self.features[0]) if self.features else None

    @property
    def last_time_ms(self) -> int | None:
        return _time_ms(self.features[-1]) if self.features else None


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _props(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature.get("properties")
    return props if isinstance(props, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _time_ms(feature: dict[str, Any]) -> int | None:
    value = _number(_props(feature).get("time"))
    return None if value is None else int(value)


def _updated_ms(feature: dict[str, Any]) -> int:
    value = _number(_props(feature).get("updated"))
    return 0 if value is None else int(value)


def validate_bbox(bbox: Sequence[float] | None) -> BBox | None:
    if bbox is None:
        return None
    if len(bbox) != 4 or not all(_number(v) is not None for v in bbox):
        raise ValueError("El recuadro debe tener cuatro números finitos: min_lon,min_lat,max_lon,max_lat")
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in bbox)
    if min_lon >= max_lon:
        raise ValueError(
            "El recuadro es inválido: min_lon debe ser menor que max_lon (no se admite el cruce del antimeridiano)"
        )
    if min_lat >= max_lat:
        raise ValueError("El recuadro es inválido: min_lat debe ser menor que max_lat")
    if not (-180 <= min_lon and max_lon <= 180 and -90 <= min_lat and max_lat <= 90):
        raise ValueError("El recuadro es inválido: longitud fuera de [-180, 180] o latitud fuera de [-90, 90]")
    return (min_lon, min_lat, max_lon, max_lat)


def _in_bbox(feature: dict[str, Any], bbox: BBox) -> bool:
    geometry = feature.get("geometry")
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return False
    lon, lat = _number(coords[0]), _number(coords[1])
    if lon is None or lat is None:
        return False
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _read_features(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"No se pudo leer el fichero {path}: {exc}") from exc
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise ValueError(f"El fichero {path} no es un FeatureCollection de GeoJSON")
    return [f for f in features if isinstance(f, dict)]


def set_fingerprint(features: Sequence[dict[str, Any]]) -> str:
    """SHA-256 of the ordered `id:updated` pairs, one per line."""
    text = "\n".join(f"{f.get('id')}:{_props(f).get('updated')}" for f in features)
    return bytes_fingerprint(text.encode("utf-8"))


def select_events(
    files: Sequence[Path | str],
    start: datetime,
    end: datetime,
    min_mag: float,
    bbox: Sequence[float] | None = None,
) -> Selection:
    """Events with start <= time < end and mag >= min_mag (null mag does not qualify)."""
    start, end = _utc(start), _utc(end)
    if end <= start:
        raise ValueError("El fin del periodo debe ser posterior al inicio")
    if _number(min_mag) is None:
        raise ValueError("La magnitud mínima debe ser un número finito")
    box = validate_bbox(bbox)
    start_ms = start.timestamp() * 1000
    end_ms = end.timestamp() * 1000

    best: dict[Any, dict[str, Any]] = {}
    dropped: set[Any] = set()
    for path in files:
        for feature in _read_features(Path(path)):
            event_id = feature.get("id")
            time_ms = _time_ms(feature)
            if event_id is None or time_ms is None or not (start_ms <= time_ms < end_ms):
                continue
            if box is not None and not _in_bbox(feature, box):
                continue
            mag = _number(_props(feature).get("mag"))
            if mag is None:
                dropped.add(event_id)
                continue
            if mag < min_mag:
                continue
            current = best.get(event_id)
            if current is None or _updated_ms(feature) > _updated_ms(current):
                best[event_id] = feature

    # An id counted as magnitude-less that also has a valid version is not dropped.
    dropped -= best.keys()
    ordered = sorted(best.values(), key=lambda f: (_time_ms(f), str(f.get("id"))))
    return Selection(
        start=start,
        end=end,
        min_magnitude=float(min_mag),
        bbox=box,
        files=tuple(str(p) for p in files),
        features=ordered,
        without_magnitude_dropped=len(dropped),
        content_sha256=set_fingerprint(ordered),
    )


# ------------------------------------------------------------ verification and record

LOCAL_CATALOG_URL = "local-catalog:data/usgs/catalog"

LOADS = """
SELECT e.extraction_id, e.window_start, e.window_end,
       (e.request_params->>'minmagnitude')::numeric AS min_magnitude,
       r.file_path, r.content_sha256
FROM extraction e
JOIN raw_payload r ON r.content_sha256 = e.content_sha256 AND r.encoding = 'file'
WHERE e.source = 'usgs_catalog' AND e.purpose = 'historical_load' AND e.outcome = 'ok'
  AND e.request_params->>'endpoint' = 'query'
  AND e.window_start < $2 AND e.window_end > $1
ORDER BY e.window_start, e.extraction_id
"""


class SelectionRejected(Exception):
    """The selection cannot be trusted; nothing is registered or published (exit code 2)."""

    exit_code = 2


def _gap(loads: list[Any], start: datetime, end: datetime) -> datetime | None:
    """First instant of [start, end) not covered by the loads' windows, or None."""
    cursor = start
    for row in sorted(loads, key=lambda r: r["window_start"]):
        if row["window_start"] > cursor:
            break
        cursor = max(cursor, row["window_end"])
        if cursor >= end:
            return None
    return cursor if cursor < end else None


async def locate_files(
    conn: asyncpg.Connection, data_dir: Path | str, start: datetime, end: datetime, min_mag: float
) -> list[Path]:
    """Files of the registered catalog loads that cover [start, end) with magnitude >= min_mag.

    Raises SelectionRejected if the period is not covered, if the minimum
    magnitude asked is below the one of the loads, or if a file is missing or
    does not match its recorded fingerprint (principle V).
    """
    start, end = _utc(start), _utc(end)
    rows = list(await conn.fetch(LOADS, start, end))
    # A load without minmagnitude holds every magnitude.
    usable = [r for r in rows if r["min_magnitude"] is None or float(r["min_magnitude"]) <= min_mag]
    gap = _gap(usable, start, end)
    if gap is not None:
        if _gap(rows, start, end) is None:
            floor = max(float(r["min_magnitude"]) for r in rows if r["min_magnitude"] is not None)
            raise SelectionRejected(
                f"La magnitud mínima pedida ({min_mag:g}) es inferior a la de la carga del catálogo "
                f"({floor:g}): faltarían eventos. Pida {floor:g} o más, o cargue el periodo con menos filtro."
            )
        raise SelectionRejected(
            f"El periodo no está cubierto por las cargas del catálogo registradas: falta desde "
            f"{gap.strftime('%Y-%m-%dT%H:%M:%SZ')}. Cargue el periodo con catalog-loader antes de reproducirlo."
        )

    base = Path(data_dir)
    paths: dict[str, Path] = {}
    for row in usable:
        if row["file_path"] in paths:
            continue
        path = base / row["file_path"]
        if not path.is_file():
            raise SelectionRejected(f"Falta el fichero del catálogo {row['file_path']}: vuelva a cargar el periodo.")
        if file_fingerprint(path) != row["content_sha256"]:
            raise SelectionRejected(
                f"El fichero {row['file_path']} no coincide con su huella registrada: ha sido alterado."
            )
        paths[row["file_path"]] = path
    return list(paths.values())


async def register_selection(conn: asyncpg.Connection, selection: Selection) -> int:
    """One core.extraction row (purpose replay_selection) describing the selection; returns its id."""
    count = selection.count
    params = {
        "start": selection.start.isoformat().replace("+00:00", "Z"),
        "end": selection.end.isoformat().replace("+00:00", "Z"),
        "min_magnitude": selection.min_magnitude,
        "bbox": list(selection.bbox) if selection.bbox is not None else None,
        "files": [{"path": f, "sha256": file_fingerprint(f)} for f in selection.files],
        "without_magnitude_dropped": selection.without_magnitude_dropped,
    }
    result = FetchResult(
        url=LOCAL_CATALOG_URL, requested_at=datetime.now(timezone.utc), outcome="ok", http_status=None,
        attempt_count=1, duration_ms=0, body=None, payload=None, error_detail=None, last_modified=None,
    )
    return await provenance.record_extraction(
        conn, result, source="usgs_catalog", purpose="replay_selection",
        counts=Counts(record=count, earthquake=count, excluded=0), fingerprint=selection.content_sha256,
        request_params=params, window=(selection.start, selection.end),
    )


set_published_count = provenance.set_published_count
