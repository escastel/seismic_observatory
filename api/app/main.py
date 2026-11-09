"""FastAPI entrypoint placeholder for the setup phase."""

import logging

from fastapi import FastAPI

from .config import ApiConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

config = ApiConfig()
app = FastAPI(title="Observatorio Sísmico", openapi_url=f"{config.api_prefix}/openapi.json")


@app.get(f"{config.api_prefix}/health")
async def health() -> dict[str, str]:
    """Expose a minimal setup health endpoint."""
    return {"status": "ok"}
