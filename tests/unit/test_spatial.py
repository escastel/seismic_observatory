"""Point-in-polygon against the delivered Natural Earth catalog (principle IV)."""

import json
import random
from pathlib import Path

import pytest

pytest.importorskip("geopandas")

from consumer.app.spatial import CatalogError, SpatialEnricher  # noqa: E402

CATALOG = Path(__file__).resolve().parents[2] / "frontend" / "public" / "datos" / "paises.geojson"


def _square(x0: float, y0: float, x1: float, y1: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _write_catalog(path: Path, entities: list[tuple[str | None, dict]]) -> str:
    features = [
        {
            "type": "Feature",
            "properties": {} if code is None else {"ADM0_A3": code},
            "geometry": geometry,
        }
        for code, geometry in entities
    ]
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return str(path)


@pytest.fixture(scope="module")
def enricher() -> SpatialEnricher:
    return SpatialEnricher(str(CATALOG))


def test_point_inside_a_country_returns_its_adm0_a3(enricher: SpatialEnricher) -> None:
    assert enricher.lookup(-3.70, 40.42) == ("ESP", False)  # Madrid
    assert enricher.lookup(139.69, 35.69) == ("JPN", False)  # Tokyo


def test_maritime_event_is_not_assigned_to_nearest_country(enricher: SpatialEnricher) -> None:
    # South-east Pacific, far from any coast: no country, never the closest one.
    assert enricher.lookup(-120.0, -20.0) == (None, False)


def test_shared_boundary_is_ambiguous_and_picks_lowest_id(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "two.geojson",
        [("BBB", _square(10, 0, 20, 10)), ("AAA", _square(0, 0, 10, 10))],
    )
    enricher = SpatialEnricher(path)
    assert enricher.lookup(10.0, 5.0) == ("AAA", True)
    assert enricher.lookup(5.0, 5.0) == ("AAA", False)
    assert enricher.lookup(15.0, 5.0) == ("BBB", False)
    assert enricher.lookup(50.0, 50.0) == (None, False)


def test_lookup_is_deterministic_over_world_points(enricher: SpatialEnricher) -> None:
    rng = random.Random(42)
    points = [(rng.uniform(-180, 180), rng.uniform(-90, 90)) for _ in range(100)]
    first = [enricher.lookup(lon, lat) for lon, lat in points]
    second = [enricher.lookup(lon, lat) for lon, lat in points]
    assert first == second


def test_repeated_adm0_a3_raises_catalog_error(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "dup.geojson",
        [("AAA", _square(0, 0, 1, 1)), ("AAA", _square(2, 2, 3, 3)), ("CCC", _square(4, 4, 5, 5))],
    )
    with pytest.raises(CatalogError, match="AAA"):
        SpatialEnricher(path)


def test_missing_adm0_a3_raises_catalog_error(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "missing.geojson",
        [("AAA", _square(0, 0, 1, 1)), (None, _square(2, 2, 3, 3))],
    )
    with pytest.raises(CatalogError, match="missing"):
        SpatialEnricher(path)


def test_verify_against_dimension(enricher: SpatialEnricher, tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path / "three.geojson",
        [("AAA", _square(0, 0, 1, 1)), ("BBB", _square(2, 2, 3, 3)), ("CCC", _square(4, 4, 5, 5))],
    )
    small = SpatialEnricher(path)
    small.verify_against_dimension({"AAA", "BBB", "CCC", "ZZZ"})
    with pytest.raises(CatalogError, match="CCC"):
        small.verify_against_dimension({"AAA", "BBB"})


def test_real_catalog_verifies_against_its_own_ids(enricher: SpatialEnricher) -> None:
    ids = set(enricher._countries["ADM0_A3"])  # noqa: SLF001
    enricher.verify_against_dimension(ids)
    with pytest.raises(CatalogError):
        enricher.verify_against_dimension(ids - {"ESP"})
