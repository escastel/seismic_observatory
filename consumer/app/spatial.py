"""Natural Earth point-in-polygon enrichment."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point


class SpatialEnricher:
    """Finds the Natural Earth entity (ADM0_A3) that contains a point.

    The identifier is the key of core.dim_country, loaded from the same file.
    A point outside every polygon (sea, Antarctic shelf...) has no country:
    lookup returns None and the panel shows «Sin país asignado».
    """

    def __init__(self, path: str) -> None:
        self._countries = gpd.read_file(Path(path)).to_crs("EPSG:4326")

    def lookup(self, longitude: float, latitude: float) -> str | None:
        point = Point(longitude, latitude)
        matches = self._countries[self._countries.geometry.intersects(point)]
        if matches.empty:
            return None
        country_id = matches.iloc[0].get("ADM0_A3")
        return str(country_id) if country_id else None
