"""Public documentation surface of the API (spec 011): /docs, redirect from /, OpenAPI contract.

Behavior tests over the real ASGI app. They do not need data: the database fixture is only
used because the shared `api` harness provides the client.
"""

from __future__ import annotations

import re

import pytest

OPENAPI = "/api/openapi.json"
DATA_PATHS = {"/api/eventos", "/api/estadisticas", "/api/salud"}
COMMON = {"mode", "start", "end", "min_mag", "country_id", "exclude_synthetic"}
EVENTS_PARAMS = COMMON | {"limit", "offset"}
STATS_PARAMS = COMMON | {"baseline_year"}
NETLIFY = "https://observatorio.netlify.app"


def spec(api) -> dict:
    response = api.get(OPENAPI)
    assert response.status == 200, response.text
    return response.json()


def operations(document: dict):
    for path, item in document["paths"].items():
        for method, operation in item.items():
            yield path, method, operation


# --- (a) /docs page ---------------------------------------------------------------------


def test_docs_page_is_html(api):
    response = api.get("/docs")
    assert response.status == 200
    assert response.headers["content-type"].startswith("text/html")


def test_docs_page_pins_swagger_ui_with_integrity(api):
    html = api.get("/docs").text
    assert "swagger-ui-dist@5.17.14" in html
    script = re.search(r"<script[^>]*swagger-ui-dist@5\.17\.14[^>]*>", html)
    style = re.search(r"<link[^>]*swagger-ui-dist@5\.17\.14[^>]*>", html)
    assert script and style, "JavaScript and CSS must both come from the pinned version"
    for tag in (script.group(0), style.group(0)):
        assert re.search(r'integrity="sha384-[A-Za-z0-9+/=]+"', tag), tag
        assert 'crossorigin="anonymous"' in tag, tag


def test_docs_page_has_no_floating_version(api):
    html = api.get("/docs").text
    assert "swagger-ui-dist@5/" not in html
    assert not re.search(r"swagger-ui-dist@\d+(/|\"|')", html)


def test_docs_page_sends_content_security_policy(api):
    policy = api.get("/docs").headers.get("content-security-policy", "")
    assert "script-src" in policy and "style-src" in policy
    assert "https://cdn.jsdelivr.net" in policy


# --- (b) root and unknown routes --------------------------------------------------------


def test_root_redirects_to_docs(api):
    response = api.get("/")
    assert response.status in (302, 307)
    assert response.headers["location"].endswith("/docs")
    assert b"error" not in response.body.lower()


@pytest.mark.parametrize("path", ["/otra-cosa", "/redoc"])
def test_unknown_routes_are_explicit_404(api, path):
    assert api.get(path).status == 404


# --- (c) interface routes stay out of the contract --------------------------------------


def test_docs_and_root_are_not_in_openapi(api):
    paths = spec(api)["paths"]
    assert "/docs" not in paths
    assert "/" not in paths


# --- (d) contract intact ----------------------------------------------------------------


def test_contract_paths_and_methods_unchanged(api):
    paths = spec(api)["paths"]
    assert set(paths) == DATA_PATHS
    for path, item in paths.items():
        assert set(item) == {"get"}, path


def parameter_names(document: dict, path: str) -> set[str]:
    return {p["name"] for p in document["paths"][path]["get"].get("parameters", [])}


def test_contract_parameter_names_unchanged(api):
    document = spec(api)
    assert parameter_names(document, "/api/eventos") == EVENTS_PARAMS
    assert parameter_names(document, "/api/estadisticas") == STATS_PARAMS
    assert parameter_names(document, "/api/salud") == set()


# --- (e) useful documentation -----------------------------------------------------------


def test_general_description_has_provenance_and_limit(api):
    description = spec(api)["info"].get("description", "")
    lowered = description.lower()
    assert "USGS" in description
    assert "no es una predicción" in lowered
    assert "evaluación de riesgo" in lowered
    assert re.search(r"60\s+peticiones\s+por\s+minuto", lowered)


def test_every_operation_has_summary_and_description(api):
    for path, method, operation in operations(spec(api)):
        assert operation.get("summary", "").strip(), f"{method} {path}: summary"
        assert operation.get("description", "").strip(), f"{method} {path}: description"


def test_every_parameter_has_description(api):
    for path, method, operation in operations(spec(api)):
        for parameter in operation.get("parameters", []):
            assert parameter.get("description", "").strip(), f"{path}: {parameter['name']}"


@pytest.mark.parametrize(
    ("path", "codes"),
    [
        ("/api/eventos", {"200", "422", "503", "500"}),
        ("/api/estadisticas", {"200", "422", "503", "500"}),
        ("/api/salud", {"200", "500"}),
    ],
)
def test_documented_responses(api, path, codes):
    responses = set(spec(api)["paths"][path]["get"]["responses"])
    assert codes <= responses, f"missing {codes - responses}"


# --- (f) read-only -----------------------------------------------------------------------


def test_no_write_operations(api):
    methods = {method for _, method, _ in operations(spec(api))}
    assert not methods & {"post", "put", "patch", "delete"}


def test_post_to_events_is_405(api):
    assert api.request("POST", "/api/eventos").status == 405


# --- (g) CORS unchanged ------------------------------------------------------------------


def preflight(api, origin: str):
    return api.request(
        "OPTIONS",
        "/api/eventos",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "ngrok-skip-browser-warning",
        },
    )


def test_cors_allows_listed_origin(api):
    response = preflight(api, NETLIFY)
    assert response.status == 200
    assert response.headers["access-control-allow-origin"] == NETLIFY
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "ngrok-skip-browser-warning" in response.headers["access-control-allow-headers"].lower()


def test_cors_rejects_unlisted_origin(api):
    response = preflight(api, "https://otro-sitio.example")
    assert "access-control-allow-origin" not in response.headers
