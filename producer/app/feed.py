"""USGS GeoJSON feed retrieval."""

from __future__ import annotations

from typing import Any

import requests


class FeedError(RuntimeError):
    """Raised when the configured earthquake feed cannot be consumed."""


def fetch_feed(url: str, timeout: float = 30.0) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FeedError(f"Unable to retrieve or decode feed {url}: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise FeedError("USGS feed is not a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise FeedError("USGS feed has no valid features collection")
    return payload
