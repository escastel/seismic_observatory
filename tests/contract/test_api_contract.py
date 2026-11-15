"""Routes and CORS of the API application (no database needed)."""

import asyncio
import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("asyncpg")

os.environ.setdefault("POSTGRES_DB", "observatory")
os.environ.setdefault("DB_READER_PASSWORD", "unused-in-this-test")
os.environ.setdefault("CORS_ORIGINS", "https://observatorio.netlify.app,http://localhost:4200")

from api.app.main import app, health  # noqa: E402


def test_required_api_routes_are_exposed() -> None:
    routes = {route.path for route in app.routes}

    assert {"/api/eventos", "/api/estadisticas/paises", "/api/estadisticas/timeline", "/api/salud"} <= routes


def test_cors_allows_only_the_configured_origins() -> None:
    cors_layers = [layer for layer in app.user_middleware if layer.cls.__name__ == "CORSMiddleware"]

    assert cors_layers
    assert cors_layers[0].kwargs["allow_origins"] == ["https://observatorio.netlify.app", "http://localhost:4200"]


class BrokenPool:
    async def fetchval(self, query: str) -> None:
        raise OSError("connection refused")


class WorkingPool:
    async def fetchval(self, query: str) -> datetime:
        assert "event_current" in query
        return datetime(2026, 11, 14, 10, 5, tzinfo=timezone.utc)


def request_with(pool: object) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))


@pytest.mark.parametrize("pool", [None, BrokenPool()], ids=["pool-not-open", "database-down"])
def test_health_answers_degraded_without_database(pool: object) -> None:
    body = asyncio.run(health(request_with(pool)))
    assert body == {"status": "degraded", "last_ingestion": None}
    assert os.environ["DB_READER_PASSWORD"] not in str(body)


def test_health_reports_the_last_ingestion() -> None:
    body = asyncio.run(health(request_with(WorkingPool())))
    assert body == {"status": "ok", "last_ingestion": "2026-11-14T10:05:00+00:00"}
