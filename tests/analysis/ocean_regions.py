"""Ocean or sea region of the events with no country (spec 008 follow-up). ANALYSIS ONLY.

    docker compose -f compose.yaml -f compose.dev.yaml run --rm tests python -m tests.analysis.ocean_regions

Read-only on the database (schema core, real data, no synthetic). Does NOT change the model, the API or the
panel, and does NOT assign a country: it groups the 2025 events of magnitude >= 4 that have no country by the
Natural Earth marine polygon (110m, public domain) that contains them. The most specific polygon wins (sea, gulf
or bay before ocean; smallest area among those). Events inside no polygon are counted apart.

The marine polygons are not versioned: download them once into the ignored data/ folder:

    mkdir -p data/naturalearth
    curl -sSL -o data/naturalearth/marine110.zip \
        https://naciscdn.org/naturalearth/110m/physical/ne_110m_geography_marine_polys.zip
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import psycopg

from tests.benchmark.index_benchmark import conninfo

MARINE = "zip://data/naturalearth/marine110.zip"
SQL = """
SELECT longitude, latitude, magnitude, depth_km
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%%' AND magnitude >= 4 AND country_id IS NULL
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
  AND longitude IS NOT NULL AND latitude IS NOT NULL
"""


def main() -> None:
    marine = gpd.read_file(MARINE)[["name", "featurecla", "scalerank", "geometry"]].copy()
    marine["name"] = marine["name"].str.title()
    marine["area"] = marine.to_crs(6933).area  # equal-area projection, only to order overlapping polygons
    with psycopg.connect(conninfo(), autocommit=True) as conn:
        rows = conn.execute(SQL).fetchall()
    events = pd.DataFrame(rows, columns=["lon", "lat", "magnitude", "depth_km"]).astype(float)
    points = gpd.GeoDataFrame(events, geometry=gpd.points_from_xy(events.lon, events.lat), crs=4326)
    points["event"] = range(len(points))
    joined = gpd.sjoin(points, marine[["name", "featurecla", "scalerank", "area", "geometry"]], how="left", predicate="within")
    joined = joined.sort_values(["event", "scalerank", "area"], ascending=[True, False, True])
    best = joined.drop_duplicates("event", keep="first").copy()
    best["name"] = best["name"].fillna("Sin region marina (fuera de todo poligono)")

    total = len(best)
    print(f"events with no country (2025, M>=4, real): {total}; marine polygons: {len(marine)}")
    grouped = best.groupby("name").agg(
        events=("event", "count"),
        median_depth_km=("depth_km", "median"),
        median_magnitude=("magnitude", "median"),
        m6_or_more=("magnitude", lambda s: int((s >= 6).sum())),
    )
    grouped["pct"] = 100 * grouped["events"] / total
    grouped = grouped.sort_values("events", ascending=False)
    print("region | events | pct | median_depth_km | median_magnitude | M>=6")
    for name, row in grouped.iterrows():
        print(f"{name} | {int(row.events)} | {row.pct:.1f} | {row.median_depth_km:.1f} | {row.median_magnitude:.1f} | {int(row.m6_or_more)}")
    by_kind = best.assign(kind=best["featurecla"].fillna("none")).groupby("kind")["event"].count()
    print("by kind:", {k: int(v) for k, v in by_kind.items()})


if __name__ == "__main__":
    main()
