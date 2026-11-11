"""Download complete USGS earthquake history for a calendar year."""

from __future__ import annotations

import argparse
import json
import logging
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)
USGS_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
PAGE_SIZE = 20_000


def fetch_year(year: int, timeout: int = 60) -> list[dict[str, Any]]:
    """Fetch every earthquake feature in ``year`` using monthly windows."""
    events: dict[str, dict[str, Any]] = {}
    for month in range(1, 13):
        start = date(year, month, 1)
        end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        offset = 1
        while True:
            response = requests.get(
                USGS_QUERY_URL,
                params={
                    "format": "geojson",
                    "starttime": start.isoformat(),
                    "endtime": end.isoformat(),
                    "orderby": "time-asc",
                    "limit": PAGE_SIZE,
                    "offset": offset,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            features = payload.get("features")
            if not isinstance(features, list):
                raise ValueError(f"USGS response for {start} is missing features")
            for feature in features:
                if not isinstance(feature, dict) or not feature.get("id"):
                    raise ValueError(f"USGS response for {start} contains an invalid feature")
                events[str(feature["id"])] = feature
            LOGGER.info("Fetched year=%d month=%02d offset=%d events=%d", year, month, offset, len(features))
            if len(features) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    return sorted(events.values(), key=lambda event: (event.get("properties", {}).get("time", 0), event["id"]))


def write_jsonl(events: list[dict[str, Any]], output: str | Path) -> int:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
            normalized = dict(event)
            normalized.update(
                {
                    "id": event.get("id"),
                    "updated": properties.get("updated", properties.get("time", event.get("updated"))),
                    "time": properties.get("time", event.get("time")),
                    "mag": properties.get("mag", event.get("mag")),
                    "place": properties.get("place", event.get("place")),
                }
            )
            handle.write(json.dumps(normalized, separators=(",", ":"), ensure_ascii=False))
            handle.write("\n")
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a complete USGS earthquake year")
    parser.add_argument("--year", type=int, required=True, help="Calendar year to download")
    parser.add_argument("--output", type=Path, required=True, help="Destination JSONL path")
    args = parser.parse_args()
    if args.year < 1900:
        raise ValueError("USGS history starts at 1900")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    events = fetch_year(args.year)
    count = write_jsonl(events, args.output)
    LOGGER.info("History complete year=%d output=%s events=%d", args.year, args.output, count)


if __name__ == "__main__":
    main()
