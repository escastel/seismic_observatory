"""Download complete USGS earthquake history for one or more calendar years."""

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


def fetch_years(
    start_year: int,
    end_year: int,
    timeout: int = 60,
) -> dict[int, list[dict[str, Any]]]:
    """Fetch every available event for each inclusive calendar year."""
    if start_year < 1900:
        raise ValueError("USGS history starts at 1900")
    if end_year < start_year:
        raise ValueError("end_year must be greater than or equal to start_year")
    return {
        year: fetch_year(year, timeout=timeout)
        for year in range(start_year, end_year + 1)
    }


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
    parser = argparse.ArgumentParser(description="Download complete USGS earthquake history")
    year_group = parser.add_mutually_exclusive_group(required=True)
    year_group.add_argument("--year", type=int, help="Calendar year to download")
    year_group.add_argument("--start-year", type=int, help="First calendar year, inclusive")
    parser.add_argument("--end-year", type=int, help="Last calendar year, inclusive")
    parser.add_argument("--output", type=Path, help="Destination JSONL path for one year")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for one historical_YYYY.jsonl file per year",
    )
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    args = parser.parse_args()
    if args.year is not None:
        if args.year < 1900:
            raise ValueError("USGS history starts at 1900")
        if args.output is None:
            raise ValueError("--output is required with --year")
        events = fetch_year(args.year, timeout=args.timeout)
        count = write_jsonl(events, args.output)
        LOGGER.info("History complete year=%d output=%s events=%d", args.year, args.output, count)
        return

    if args.end_year is None or args.output_dir is None:
        raise ValueError("--start-year requires --end-year and --output-dir")
    histories = fetch_years(args.start_year, args.end_year, timeout=args.timeout)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for year, events in histories.items():
        output = args.output_dir / f"historical_{year}.jsonl"
        count = write_jsonl(events, output)
        LOGGER.info("History complete year=%d output=%s events=%d", year, output, count)


if __name__ == "__main__":
    main()
