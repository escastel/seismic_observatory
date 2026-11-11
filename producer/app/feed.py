"""USGS GeoJSON feed retrieval."""

from __future__ import annotations

from typing import Any
import logging
import time

import requests

logger = logging.getLogger(__name__)

class FeedError(RuntimeError):
    """Raised when the configured earthquake feed cannot be consumed."""


def fetch_feed(url: str, timeout: float = 30.0, max_retries: int = 3) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    logger.warning(
                        "USGS feed temporary HTTP failure status=%s retry_in=%ss attempt=%s",
                        response.status_code, delay, attempt + 1,
                    )
                    time.sleep(delay)
                    continue
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError) as exc:
            if attempt >= max_retries:
                raise FeedError(f"Unable to retrieve or decode feed {url}: {exc}") from exc
            delay = 2**attempt
            logger.warning("USGS feed request failed retry_in=%ss attempt=%s", delay, attempt + 1)
            time.sleep(delay)
    else:
        raise FeedError(f"Unable to retrieve feed {url}")

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise FeedError("USGS feed is not a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise FeedError("USGS feed has no valid features collection")
    filtered: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict):
            raise FeedError("USGS feed contains a non-object feature")
        properties = feature.get("properties") or {}
        if properties.get("type") == "earthquake":
            filtered.append(feature)
    payload["features"] = filtered
    return payload
