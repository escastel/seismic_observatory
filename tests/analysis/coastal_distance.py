"""Distance from "Sin país asignado" events to the nearest country polygon (spec 008 follow-up).

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.analysis.coastal_distance

Read-only. Real data only (schema core, no synthetic). For each event of 2025 with magnitude >= 4 and no country,
finds the nearest polygon of the delivered Natural Earth copy (frontend/public/datos/paises.geojson) and reports the
great-circle distance in km to the nearest point of that polygon, in distance bands. The nearest point is found in
planar lon/lat (small error at high latitudes); the longitude is also tried shifted by +-360 degrees so polygons
across the antimeridian are not missed. This does NOT assign a country: it only describes how far from land the
unassigned events are.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import psycopg
from shapely import STRtree
from shapely.geometry import Point, shape
from shapely.ops import nearest_points

from tests.benchmark.index_benchmark import conninfo

GEOJSON = Path("frontend/public/datos/paises.geojson")
BANDS = [(0, 10), (10, 50), (50, 100), (100, 200), (200, 500), (500, float("inf"))]
SQL = """
SELECT longitude, latitude, magnitude
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%%' AND magnitude >= 4 AND country_id IS NULL
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
  AND longitude IS NOT NULL AND latitude IS NOT NULL
"""


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def load_polygons() -> tuple[list, int]:
    data = json.loads(GEOJSON.read_text(encoding="utf-8"))
    geoms = [shape(feature["geometry"]) for feature in data["features"]]
    vertices = sum(len(ring.coords) for g in geoms for poly in getattr(g, "geoms", [g]) for ring in [poly.exterior])
    return geoms, vertices


def distance_to_land_km(tree: STRtree, geoms: list, lon: float, lat: float) -> float:
    best = float("inf")
    for shift in (0.0, -360.0, 360.0):
        point = Point(lon + shift, lat)
        index = int(tree.nearest(point))
        land = nearest_points(point, geoms[index])[1]
        best = min(best, haversine_km(lon + shift, lat, land.x, land.y))
    return best


def main() -> None:
    geoms, vertices = load_polygons()
    tree = STRtree(geoms)
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        rows = conn.execute(SQL).fetchall()
    distances = sorted(distance_to_land_km(tree, geoms, float(lon), float(lat)) for lon, lat, _ in rows)
    total = len(distances)
    print(f"polygons: {len(geoms)}; exterior vertices: {vertices} (mean {vertices / len(geoms):.0f} per entity)")
    print(f"events with no country (2025, M>=4, real): {total}")
    print("band_km | events | pct | cumulative_pct")
    cumulative = 0
    for low, high in BANDS:
        count = sum(1 for d in distances if low <= d < high)
        cumulative += count
        label = f"{low}-{high}" if high != float("inf") else f">={low}"
        print(f"{label} | {count} | {100 * count / total:.1f} | {100 * cumulative / total:.1f}")
    def pct(q: float) -> float:
        return distances[min(total - 1, int(q * total))]
    print(f"median_km {pct(0.5):.1f}; p25 {pct(0.25):.1f}; p75 {pct(0.75):.1f}; p95 {pct(0.95):.1f}; max {distances[-1]:.1f}")


if __name__ == "__main__":
    main()
