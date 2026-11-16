"""Heartbeat file written after each successful cycle, and its health check.

    python -m common.health --max-age 180

exits 0 when the heartbeat is younger than --max-age seconds and 1 otherwise
(missing or old). Compose uses it as the producer and consumer healthcheck,
with --max-age set to three cycle intervals.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

DEFAULT_PATH = Path(os.environ.get("HEARTBEAT_FILE", "/tmp/observatory-heartbeat"))


class Heartbeat:
    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = Path(path)

    def beat(self, now: float | None = None) -> None:
        """Record a successful cycle (atomic replace, so a reader never sees half a file)."""
        moment = time.time() if now is None else now
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(f"{moment:.3f}\n", encoding="utf-8")
        os.replace(temporary, self.path)


def age_seconds(path: Path | str = DEFAULT_PATH, now: float | None = None) -> float | None:
    """Seconds since the last beat, or None when there has never been one."""
    try:
        last = float(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return (time.time() if now is None else now) - last


def is_fresh(max_age: float, path: Path | str = DEFAULT_PATH, now: float | None = None) -> bool:
    age = age_seconds(path, now)
    return age is not None and age <= max_age


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail when the service heartbeat is missing or old")
    parser.add_argument("--max-age", type=float, required=True, help="maximum age in seconds")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    age = age_seconds(args.path)
    if age is None:
        print(f"unhealthy: no heartbeat at {args.path}")
        return 1
    if age > args.max_age:
        print(f"unhealthy: last heartbeat {age:.0f} s ago (limit {args.max_age:.0f} s)")
        return 1
    print(f"healthy: last heartbeat {age:.0f} s ago")
    return 0


if __name__ == "__main__":
    sys.exit(main())
