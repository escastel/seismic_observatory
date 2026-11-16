"""API latency benchmark (spec 006, research.md R10, SC-008, quickstart V16).

    python3 tests/benchmark/api_latency.py [--base-url URL] [--runs 30] [--warmup 5] [--json]

Inside the compose network use --base-url http://api:8000. Read-only: GET only.
Measures three result sizes, sequentially, after the warm-up requests:
  1. small page: /api/eventos?limit=10 (live, narrow window)
  2. full page: /api/eventos?limit=1000 over 2025
  3. statistics: /api/estadisticas over 2025 with min_mag=4
The mode (live or replay) is chosen by probing whether live has 2025 data.
Exit code 1 if any median exceeds 2000 ms or any request fails.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LIMIT_MS = 2000.0
YEAR_START = "2025-01-01T00:00:00Z"
YEAR_END = "2026-01-01T00:00:00Z"
SMALL_START = "2025-12-31T00:00:00Z"
TIMEOUT_S = 60


def get_json(base_url: str, path: str, params: dict) -> tuple[dict, float]:
    url = base_url.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
        body = response.read()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return json.loads(body), elapsed_ms


def cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def ram_gib() -> float | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal"):
                    return round(int(line.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    try:
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("load", ctypes.c_ulong),
                    ("total_phys", ctypes.c_ulonglong),
                    ("avail_phys", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong),
                    ("avail_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("avail_virtual", ctypes.c_ulonglong),
                    ("avail_ext", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return round(status.total_phys / 1024**3, 1)
    except Exception:  # noqa: BLE001 - best effort only
        pass
    return None


def docker_version() -> str:
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=10, check=False
        )
        return result.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - docker may be absent (e.g. inside the tests container)
        return "not available"


def machine_info() -> dict:
    return {
        "cpu": cpu_model(),
        "logical_cores": os.cpu_count(),
        "ram_gib": ram_gib(),
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "docker": docker_version(),
        "python": platform.python_version(),
    }


def choose_mode(base_url: str) -> tuple[str, int]:
    """Return (mode, total of 2025 events in that mode)."""
    probe, _ = get_json(
        base_url, "/api/eventos", {"start": YEAR_START, "end": YEAR_END, "limit": 1}
    )
    live_total = int(probe["metadata"]["total"])
    if live_total > 0:
        return "live", live_total
    probe, _ = get_json(
        base_url,
        "/api/eventos",
        {"mode": "replay", "start": YEAR_START, "end": YEAR_END, "limit": 1},
    )
    return "replay", int(probe["metadata"]["total"])


def measure(base_url: str, path: str, params: dict, runs: int, warmup: int) -> dict:
    total = None
    timings: list[float] = []
    errors: list[str] = []
    for index in range(warmup + runs):
        try:
            payload, elapsed = get_json(base_url, path, params)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if total is None:
            total = payload.get("metadata", {}).get("total", payload.get("total"))
        if index >= warmup:
            timings.append(elapsed)
    result = {"total_events": total, "errors": errors, "runs_ok": len(timings)}
    if timings:
        ordered = sorted(timings)
        p95_index = min(len(ordered) - 1, max(0, round(0.95 * len(ordered)) - 1))
        result.update(
            median_ms=statistics.median(ordered),
            p95_ms=ordered[p95_index],
            max_ms=ordered[-1],
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base URL (inside the compose network: http://api:8000)",
    )
    parser.add_argument("--runs", type=int, default=30, help="measured requests per size")
    parser.add_argument("--warmup", type=int, default=5, help="warm-up requests per size")
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    args = parser.parse_args()

    info = machine_info()
    try:
        mode, year_total = choose_mode(args.base_url)
    except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
        print(f"ERROR: cannot probe the API at {args.base_url}: {exc}", file=sys.stderr)
        return 1
    schema = "core" if mode == "live" else "replay"
    mode_param = {} if mode == "live" else {"mode": "replay"}

    cases = [
        (
            "small page (limit=10)",
            "/api/eventos",
            {"limit": 10, "start": SMALL_START, "end": YEAR_END, **mode_param},
        ),
        (
            "full page (limit=1000)",
            "/api/eventos",
            {"limit": 1000, "start": YEAR_START, "end": YEAR_END, **mode_param},
        ),
        (
            "statistics (year, min_mag=4)",
            "/api/estadisticas",
            {"start": YEAR_START, "end": YEAR_END, "min_mag": 4, **mode_param},
        ),
    ]
    rows = []
    for name, path, params in cases:
        outcome = measure(args.base_url, path, params, args.runs, args.warmup)
        rows.append({"name": name, "path": path, "params": params, **outcome})

    failed = any(row["errors"] or "median_ms" not in row for row in rows)
    exceeded = any(row.get("median_ms", 0.0) > LIMIT_MS for row in rows)
    report = {
        "base_url": args.base_url,
        "mode": mode,
        "schema": schema,
        "events_2025": year_total,
        "runs": args.runs,
        "warmup": args.warmup,
        "limit_ms": LIMIT_MS,
        "machine": info,
        "results": rows,
        "passed": not (failed or exceeded),
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Base URL: {args.base_url}")
        print(f"Mode: {mode} (schema {schema}); 2025 events in that mode: {year_total}")
        print(f"Machine: {info['cpu']}; {info['logical_cores']} logical cores; "
              f"RAM {info['ram_gib']} GiB")
        print(f"OS: {info['os']}; Docker: {info['docker']}")
        print(f"Runs: {args.runs} after {args.warmup} warm-up; sequential GET requests\n")
        header = f"{'name':<30}{'events':>10}{'median':>10}{'p95':>10}{'max':>10}  (ms)"
        print(header)
        print("-" * len(header))
        for row in rows:
            if "median_ms" in row:
                print(f"{row['name']:<30}{str(row['total_events']):>10}"
                      f"{row['median_ms']:>10.1f}{row['p95_ms']:>10.1f}{row['max_ms']:>10.1f}")
            else:
                print(f"{row['name']:<30}{str(row['total_events']):>10}{'FAILED':>10}")
            for error in row["errors"][:3]:
                print(f"  error: {error}")
        print(f"\nSC-008 (median <= {LIMIT_MS:.0f} ms, no failures): "
              f"{'PASS' if report['passed'] else 'FAIL'}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
