from pathlib import Path

ROOT = Path(__file__).parents[2]
MAIN = (ROOT / "api/app/main.py").read_text(encoding="utf-8")
QUERIES = (ROOT / "api/app/queries.py").read_text(encoding="utf-8")
SCHEMAS = (ROOT / "api/app/schemas.py").read_text(encoding="utf-8")


def test_annex_routes_and_contract_fields_are_present() -> None:
    assert '@app.get(f"{config.api_prefix}/salud")' in MAIN
    assert '@app.get(f"{config.api_prefix}/estadisticas")' in MAIN
    assert '@app.get(f"{config.api_prefix}/eventos")' in MAIN
    assert "last_ingestion" in MAIN
    assert "truncated" in MAIN
    assert "ngrok-skip-browser-warning" in MAIN


def test_contract_supports_exclusive_end_and_24_hour_default() -> None:
    assert "timedelta(days=1)" in MAIN
    assert 'f.event_time < ?' in QUERIES


def test_geojson_contract_includes_empty_collection_and_metadata() -> None:
    assert 'type: Literal["FeatureCollection"] = "FeatureCollection"' in SCHEMAS
    assert "features: list[dict[str, Any]]" in SCHEMAS
    assert '"generated"' in MAIN
    assert '"total"' in MAIN


def test_pagination_and_truncation_are_explicit() -> None:
    assert "limit: int = Query(default=1000, ge=1, le=10000)" in MAIN
    assert "offset: int = Query(default=0, ge=0)" in MAIN
    assert "filters.offset + len(features) < total" in MAIN


def test_contract_exposes_null_safe_event_properties() -> None:
    assert "mag_type: str | None" in SCHEMAS
    assert "depth_km: float | None" in SCHEMAS
    assert "country_id: str | None" in SCHEMAS


def test_equivalent_filters_reach_event_and_statistics_queries() -> None:
    assert "country_id" in QUERIES
    assert "min_magnitude" in QUERIES
    assert "max_magnitude" in QUERIES
    assert "def country_stats" in QUERIES
    assert "def timeline_stats" in QUERIES


def test_cors_is_configurable_for_netlify_and_ngrok() -> None:
    assert "CORSMiddleware" in MAIN
    assert "allow_origins=origins" in MAIN
    assert '"ngrok-skip-browser-warning"' in MAIN
