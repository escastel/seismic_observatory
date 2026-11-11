from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_frontend_consumes_contract_metadata_and_filters() -> None:
    source = (ROOT / "frontend/src/app/app.component.ts").read_text(encoding="utf-8")
    template = (ROOT / "frontend/src/app/app.component.html").read_text(encoding="utf-8")
    for token in ("countryFilter", "startFilter", "endFilter", "minMagnitudeFilter", "truncated"):
        assert token in source or token in template
    for token in ("country_name", "magType", "last_ingestion", "total"):
        assert token in source
