"""Point-in-polygon against the delivered Natural Earth catalog (principle IV)."""

from pathlib import Path

import pytest

pytest.importorskip("geopandas")

from consumer.app.spatial import SpatialEnricher  # noqa: E402

CATALOG = Path(__file__).resolve().parents[2] / "frontend" / "public" / "datos" / "paises.geojson"


@pytest.fixture(scope="module")
def enricher() -> SpatialEnricher:
    return SpatialEnricher(str(CATALOG))


def test_point_inside_a_country_returns_its_adm0_a3(enricher: SpatialEnricher) -> None:
    assert enricher.lookup(-3.70, 40.42) == "ESP"  # Madrid
    assert enricher.lookup(139.69, 35.69) == "JPN"  # Tokyo


def test_maritime_event_is_not_assigned_to_nearest_country(enricher: SpatialEnricher) -> None:
    # South-east Pacific, far from any coast: no country, never the closest one.
    assert enricher.lookup(-120.0, -20.0) is None
