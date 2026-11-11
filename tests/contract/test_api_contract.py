import os

import pytest


pytest.importorskip("fastapi")
pytest.importorskip("asyncpg")
pytest.importorskip("ngrok")

os.environ.setdefault("DATABASE_DSN", "postgresql://test:test@localhost/test")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("API_PREFIX", "/api")

from api.app.main import app  # noqa: E402


def test_required_api_routes_are_exposed() -> None:
    routes = {route.path for route in app.routes}

    assert {"/api/eventos", "/api/estadisticas/paises", "/api/estadisticas/timeline"} <= routes


def test_cors_middleware_is_configured_for_frontend_access() -> None:
    cors_layers = [
        layer
        for layer in app.user_middleware
        if layer.cls.__name__ == "CORSMiddleware"
    ]

    assert cors_layers
    assert cors_layers[0].kwargs["allow_origins"] == ["*"]
