"""Natural Earth point-in-polygon enrichment."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point


class CatalogError(RuntimeError):
    """The country catalog is unusable or inconsistent with core.dim_country."""


class SpatialEnricher:
    """Finds the Natural Earth entity (ADM0_A3) that contains a point.

    The identifier is the key of core.dim_country, loaded from the same file.
    A point outside every polygon (sea, Antarctic shelf...) has no country:
    lookup returns (None, False) and the panel shows «Sin país asignado».
    """

    def __init__(self, path: str) -> None:
        countries = gpd.read_file(Path(path)).to_crs("EPSG:4326")
        if "ADM0_A3" not in countries.columns:
            raise CatalogError(f"Catalog {path} has no ADM0_A3 property")
        ids = countries["ADM0_A3"]
        blank = ids.isna() | (ids.astype(str).str.strip() == "")
        repeated = sorted(set(ids[~blank][ids[~blank].duplicated(keep=False)].astype(str)))
        problems = []
        if blank.any():
            problems.append(f"{int(blank.sum())} entities missing ADM0_A3")
        if repeated:
            problems.append(f"repeated ADM0_A3: {', '.join(repeated)}")
        if problems:
            raise CatalogError(f"Invalid catalog {path}: " + "; ".join(problems))
        self._countries = countries.sort_values("ADM0_A3").reset_index(drop=True)

    def lookup(self, longitude: float, latitude: float) -> tuple[str | None, bool]:
        point = Point(longitude, latitude)
        matches = self._countries[self._countries.geometry.intersects(point)]
        if matches.empty:
            return None, False
        return str(matches.iloc[0]["ADM0_A3"]), len(matches) > 1

    def verify_against_dimension(self, ids: set[str]) -> None:
        missing = sorted(set(self._countries["ADM0_A3"].astype(str)) - set(ids))
        if missing:
            raise CatalogError(f"Catalog ids missing from core.dim_country: {', '.join(missing)}")
