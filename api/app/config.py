"""Configuration for the FastAPI service."""

from dataclasses import dataclass
import os


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class ApiConfig:
    database_dsn: str = _required_env("DATABASE_DSN")
    cors_origins: str = _required_env("CORS_ORIGINS")
    api_prefix: str = _required_env("API_PREFIX")
