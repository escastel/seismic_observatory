"""HTTP contract of the API (spec 006): routes, methods, CORS and parameter errors.

No database: the real application is driven through the ASGI client with its pools unset
(or replaced by fakes), so everything checked here happens before any query.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("asyncpg")

os.environ.setdefault("POSTGRES_DB", "observatory")
os.environ.setdefault("DB_READER_PASSWORD", "unused-in-this-test")
os.environ.setdefault("CORS_ORIGINS", "https://observatorio.netlify.app,http://localhost:4200")

from api.app.main import app  # noqa: E402
from tests.support.asgi_client import Response, call_asgi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROUTES = {"/api/eventos", "/api/estadisticas", "/api/salud", "/api/openapi.json"}
ALLOWED_ORIGINS = [origin.strip() for origin in os.environ["CORS_ORIGINS"].split(",") if origin.strip()]
FOREIGN_ORIGIN = "https://evil.example.com"


@pytest.fixture(autouse=True)
def pools_not_open():
    """Every test starts with pools set to None (as before the lifespan opens them)."""
    saved = getattr(app.state, "pools", None)
    app.state.pools = {"live": None, "replay": None}
    yield
    app.state.pools = saved


def call(method: str, path: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Response:
    return asyncio.run(call_asgi(app, method, path, params, headers))


def preflight(origin: str, path: str = "/api/eventos") -> Response:
    return call(
        "OPTIONS",
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "ngrok-skip-browser-warning",
        },
    )


def tokens(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


# --- routes and methods ------------------------------------------------------------------


def test_the_exposed_routes_are_exactly_the_contract_ones() -> None:
    paths = {route.path for route in app.routes}

    assert paths == EXPECTED_ROUTES


@pytest.mark.parametrize("path", sorted(EXPECTED_ROUTES))
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_no_route_accepts_a_write_method(path: str, method: str) -> None:
    response = call(method, path)

    assert response.status == 405


@pytest.mark.parametrize(
    "path", ["/docs", "/redoc", "/api/docs", "/api/redoc", "/openapi.json", "/api/admin", "/api/replay", "/api/reset", "/"]
)
def test_no_documentation_or_administration_route(path: str) -> None:
    assert call("GET", path).status == 404


def test_openapi_document_is_served_under_the_prefix() -> None:
    response = call("GET", "/api/openapi.json")

    assert response.status == 200
    document = response.json()
    assert set(document["paths"]) == EXPECTED_ROUTES - {"/api/openapi.json"}
    for operations in document["paths"].values():
        assert set(operations) == {"get"}


# --- CORS --------------------------------------------------------------------------------


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_preflight_from_an_allowed_origin(origin: str) -> None:
    response = preflight(origin)

    assert response.status == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert tokens(response.headers["access-control-allow-methods"]) == {"get", "options"}
    assert "ngrok-skip-browser-warning" in tokens(response.headers["access-control-allow-headers"])
    assert "access-control-allow-credentials" not in response.headers


def test_the_default_development_origin_is_allowed() -> None:
    if "http://localhost:4200" not in ALLOWED_ORIGINS:
        pytest.skip("CORS_ORIGINS of this environment does not include the development origin")

    assert preflight("http://localhost:4200").headers["access-control-allow-origin"] == "http://localhost:4200"


def test_preflight_from_another_origin_gets_no_access_headers() -> None:
    response = preflight(FOREIGN_ORIGIN)

    # Without access-control-allow-origin the browser refuses the request.
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
    assert response.status >= 400


def test_preflight_of_a_write_method_is_not_allowed() -> None:
    response = call(
        "OPTIONS",
        "/api/eventos",
        headers={
            "Origin": ALLOWED_ORIGINS[0],
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status >= 400


def test_a_simple_request_from_an_allowed_origin_carries_the_origin_header() -> None:
    response = call("GET", "/api/salud", headers={"Origin": ALLOWED_ORIGINS[0]})

    assert response.status == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGINS[0]
    assert "access-control-allow-credentials" not in response.headers


def test_a_simple_request_from_another_origin_gets_no_access_headers() -> None:
    response = call("GET", "/api/salud", headers={"Origin": FOREIGN_ORIGIN})

    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


# --- parameter errors --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "param"),
    [
        ({"mode": "x"}, "mode"),
        ({"start": "2026-03-01T00:00:00"}, "start"),
        ({"start": "2026-03-02T00:00:00Z", "end": "2026-03-01T00:00:00Z"}, "start"),
        ({"start": "2026-03-01T00:00:00Z", "end": "2026-03-01T00:00:00Z"}, "start"),
        ({"min_mag": "abc"}, "min_mag"),
        ({"min_mag": "nan"}, "min_mag"),
        ({"limit": 0}, "limit"),
        ({"offset": -1}, "offset"),
        ({"country_id": "not valid!"}, "country_id"),
    ],
)
def test_invalid_event_parameters_are_422_naming_the_parameter(params: dict[str, Any], param: str) -> None:
    response = call("GET", "/api/eventos", params)

    assert response.status == 422
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["error"] == "invalid_parameters"
    assert body["detail"], body
    entry = body["detail"][0]
    assert entry["param"] == param
    assert isinstance(entry["message"], str) and entry["message"]


@pytest.mark.parametrize(
    ("params", "param"),
    [({"mode": "x"}, "mode"), ({"min_mag": "abc"}, "min_mag"), ({"baseline_year": "abc"}, "baseline_year")],
)
def test_invalid_statistics_parameters_are_422(params: dict[str, Any], param: str) -> None:
    response = call("GET", "/api/estadisticas", params)

    assert response.status == 422
    body = response.json()
    assert body["error"] == "invalid_parameters"
    assert body["detail"][0]["param"] == param


@pytest.mark.parametrize("path", ["/api/eventos", "/api/estadisticas"])
@pytest.mark.parametrize("params", [{"format": "geojson"}, {"country": "Chile"}, {"format": "geojson", "country": "Chile"}])
def test_unknown_parameters_are_ignored(path: str, params: dict[str, Any]) -> None:
    response = call("GET", path, params)

    # Valid request: it only fails later, for lack of a database, never as a parameter error.
    assert response.status == 503
    assert response.json()["error"] == "database_unavailable"


def test_unknown_parameters_do_not_affect_the_health_endpoint() -> None:
    assert call("GET", "/api/salud", {"format": "geojson"}).status == 200


# --- database failures are explicit ------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/eventos", "/api/estadisticas"])
def test_without_an_open_pool_queries_answer_503_never_an_empty_200(path: str) -> None:
    response = call("GET", path)

    assert response.status == 503
    body = response.json()
    assert body["error"] == "database_unavailable"
    assert "features" not in body
    assert os.environ["DB_READER_PASSWORD"] not in response.text


class BrokenPool:
    async def fetchval(self, *args: Any, **kwargs: Any) -> None:
        raise OSError("connection refused")


def test_health_is_200_and_degraded_without_database() -> None:
    for pools in (
        {"live": None, "replay": None},
        {"live": BrokenPool(), "replay": BrokenPool()},
    ):
        app.state.pools = pools

        response = call("GET", "/api/salud")

        assert response.status == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"] == "unavailable" and body["replay_database"] == "unavailable"
        assert body["last_ingestion"] is None
        assert isinstance(body["generated"], int)
        assert os.environ["DB_READER_PASSWORD"] not in response.text


# --- the API never reaches USGS or Kafka -------------------------------------------------


def test_importing_the_api_does_not_load_usgs_or_kafka_clients() -> None:
    code = (
        "import sys, api.app.main\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "{'aiokafka', 'kafka', 'confluent_kafka', 'producer', 'consumer'} or m == 'common.topics']\n"
        "print(','.join(sorted(bad)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=dict(os.environ), capture_output=True, text=True, timeout=120
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
