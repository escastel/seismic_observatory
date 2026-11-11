import pytest


pytest.importorskip("geopandas")

from consumer.app.spatial import SpatialEnricher, UNASSIGNED_COUNTRY


class EmptyMatches:
    empty = True


class EmptyCountries:
    geometry = object()

    def __getitem__(self, key: object) -> EmptyMatches:
        return EmptyMatches()


def test_maritime_event_is_not_assigned_to_nearest_country() -> None:
    enricher = SpatialEnricher.__new__(SpatialEnricher)
    enricher._countries = EmptyCountries()
    enricher._source_dataset = "paises.geojson"
    enricher._geometry_hash = "test-hash"

    geography = enricher.lookup(-120.0, -20.0)

    assert geography.country == UNASSIGNED_COUNTRY
    assert geography.continent == "Sin continente asignado"
    assert geography.subregion == "Sin subregión asignada"
