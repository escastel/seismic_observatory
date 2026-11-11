"""Reproducible quantitative checks for SC-001, SC-005 and SC-006."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen


def percentile(values: list[float], percentile_rank: float) -> float:
    if not values:
        raise ValueError("at least one measurement is required")
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentile_rank / 100) * (len(ordered) - 1)))
    return ordered[index]


def check_api(base_url: str, requests_count: int) -> tuple[float, float]:
    latencies: list[float] = []
    successes = 0
    for _ in range(requests_count):
        started = time.perf_counter()
        request = Request(f"{base_url.rstrip('/')}/api/eventos?limit=1")
        try:
            with urlopen(request, timeout=10) as response:
                if 200 <= response.status < 300:
                    successes += 1
        except OSError:
            pass
        latencies.append(time.perf_counter() - started)
    return successes / requests_count, percentile(latencies, 95)


def check_replay(replay_file: Path, rate: float) -> float:
    if rate <= 0:
        raise ValueError("replay rate must be positive")
    started = time.perf_counter()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "producer",
            "python",
            "-m",
            "app.replay",
            "--path",
            f"/data/seeds/{replay_file.name}",
            "--rate",
            str(rate),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "replay command failed")
    events = sum(1 for line in replay_file.read_text(encoding="utf-8").splitlines() if line.strip())
    return events / elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--replay-file", type=Path)
    parser.add_argument("--replay-rate", type=float, default=10.0)
    args = parser.parse_args()

    success_rate, p95 = check_api(args.base_url, args.requests)
    print(json.dumps({"SC-001_success_rate": success_rate, "SC-005_p95_seconds": p95}))
    if success_rate < 0.99 or p95 >= 2.0:
        return 1

    if args.replay_file is not None:
        throughput = check_replay(args.replay_file, args.replay_rate)
        baseline = 1 / 60
        print(json.dumps({"SC-006_replay_throughput": throughput, "SC-006_baseline_10x": baseline * 10}))
        if throughput < baseline * 10:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
