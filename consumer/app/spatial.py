"""Natural Earth point-in-polygon enrichment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point


UNASSIGNED_COUNTRY = "Sin país asignado"


@dataclass(frozen=True)
class Geography:
    country: str
    continent: str
    subregion: str
    source_dataset: str
    geometry_hash: str


class SpatialEnricher:
    def __init__(self, path: str) -> None:
        dataset_path = Path(path)
        self._source_dataset = dataset_path.name
        self._geometry_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        self._countries = gpd.read_file(dataset_path).to_crs("EPSG:4326")

    def lookup(self, longitude: float, latitude: float) -> Geography:
        point = Point(longitude, latitude)
        matches = self._countries[self._countries.geometry.intersects(point)]
        if matches.empty:
            return Geography(
                UNASSIGNED_COUNTRY,
                "Sin continente asignado",
                "Sin subregión asignada",
                self._source_dataset,
                self._geometry_hash,
            )
        row = matches.iloc[0]
        return Geography(
            str(row.get("NAME") or row.get("ADMIN") or UNASSIGNED_COUNTRY),
            str(row.get("CONTINENT") or "Sin continente asignado"),
            str(row.get("SUBREGION") or "Sin subregión asignada"),
            self._source_dataset,
            self._geometry_hash,
        )
