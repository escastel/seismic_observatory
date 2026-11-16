"""Manual load of the USGS catalog into core (contracts/catalog-loader.md).

    docker compose run --rm catalog-loader [options]

Without options it runs the mandatory load: 2025, world, magnitude >= 4,
earthquakes. For every calendar month of the period:

1. ask /count (recorded); split the interval while it exceeds maxAllowed;
2. download /query (recorded) and check that it returns exactly the declared
   events; keep the answer unmodified under DATA_DIR/usgs/catalog/;
3. publish to earthquakes.catalog the versions not yet in core.publish_state.

An interval whose file is on disk with its recorded fingerprint is reused, so
repeating the command continues an interrupted load and publishes nothing
twice. Exit codes: 0 complete, 1 error, 2 bad arguments, 3 difference with
the total declared by USGS.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from aiokafka import AIOKafkaProducer

from common.db import create_pool
from common.logging import configure
from common.retry import retry
from common.settings import CatalogLoaderSettings
from common.settings import catalog_loader as load_settings
from common.topics import ensure_topics

from . import provenance
from .catalog import (
    Filters,
    Interval,
    IntervalTooLarge,
    file_name,
    iso,
    limit_exceeded,
    month_intervals,
    plan_intervals,
    recorded_params,
)
from .classify import classify
from .fingerprint import bytes_fingerprint, file_fingerprint
from .provenance import Counts
from .publisher import publish_versions
from .usgs import FetchResult, fetch_async

logger = logging.getLogger(__name__)

SOURCE = "usgs_catalog"
PURPOSES = ("historical_load", "gap_recovery")
DEFAULT_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
DEFAULT_END = datetime(2026, 1, 1, tzinfo=timezone.utc)
CATALOG_SUBDIR = Path("usgs") / "catalog"

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_DIFFERENCE = 0, 1, 2, 3


class UsageError(ValueError):
    """Invalid arguments: nothing is asked to USGS (exit code 2)."""


class LoadError(RuntimeError):
    """The load cannot finish; what was done is kept and repeating continues (exit code 1)."""


# --------------------------------------------------------------------- arguments


@dataclass(frozen=True)
class LoadRequest:
    start: datetime
    end: datetime
    filters: Filters
    purpose: str
    refresh: bool = False
    dry_run: bool = False
    list_gaps: bool = False


def parse_instant(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise UsageError(f"unreadable date {text!r}: use ISO 8601, for example 2025-01-01 or 2025-01-01T00:00:00Z") from exc
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would call sys.exit
        raise UsageError(message)


def parse_request(argv: list[str], now: datetime) -> LoadRequest:
    parser = _Parser(prog="catalog-loader", description="Load the USGS catalog into the real schema")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--min-magnitude")
    parser.add_argument("--all-magnitudes", action="store_true")
    parser.add_argument("--event-type")
    parser.add_argument("--all-types", action="store_true")
    parser.add_argument("--purpose", default="historical_load")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gaps", action="store_true")
    args = parser.parse_args(argv)

    if args.purpose not in PURPOSES:
        raise UsageError(f"--purpose must be one of {', '.join(PURPOSES)}")
    gap = args.purpose == "gap_recovery"
    if gap and not (args.start and args.end):
        raise UsageError("--purpose gap_recovery needs --start and --end (the producer's warning or --gaps gives them)")

    start = parse_instant(args.start) if args.start else DEFAULT_START
    end = parse_instant(args.end) if args.end else DEFAULT_END
    if not args.gaps:
        if end <= start:
            raise UsageError(f"the end ({iso(end)}) must be after the start ({iso(start)})")
        if end > now:
            raise UsageError(f"the end ({iso(end)}) is in the future; the catalog only holds past events")

    if args.all_magnitudes or (gap and args.min_magnitude is None):
        min_magnitude = None
    elif args.min_magnitude is not None:
        try:
            min_magnitude = float(args.min_magnitude)
        except ValueError as exc:
            raise UsageError(f"--min-magnitude must be a number, got {args.min_magnitude!r}") from exc
    else:
        min_magnitude = 4.0
    if args.all_types or (gap and args.event_type is None):
        event_type = None
    else:
        event_type = args.event_type or "earthquake"

    return LoadRequest(start, end, Filters(min_magnitude, event_type), args.purpose,
                       args.refresh, args.dry_run, args.gaps)


# ------------------------------------------------------------------------ result


@dataclass
class IntervalReport:
    interval: Interval
    declared: int
    received: int | None = None
    earthquakes: int | None = None
    excluded: int | None = None
    published: int | None = None
    file_status: str = "—"           # descargado | reutilizado | prueba


@dataclass
class Summary:
    request: LoadRequest
    intervals: list[IntervalReport] = field(default_factory=list)
    repeated: int = 0
    distinct: int = 0
    declared_total: int | None = None
    finished_at: datetime | None = None

    @property
    def difference(self) -> int | None:
        if self.declared_total is None or self.request.dry_run:
            return None
        return self.distinct - self.declared_total

    @property
    def exit_code(self) -> int:
        return EXIT_OK if self.difference in (0, None) else EXIT_DIFFERENCE

    def to_json(self) -> dict[str, Any]:
        return {
            "period": {"start": iso(self.request.start), "end": iso(self.request.end)},
            "filters": asdict(self.request.filters),
            "purpose": self.request.purpose,
            "finished_at": iso(self.finished_at) if self.finished_at else None,
            "intervals": [
                {**{k: v for k, v in asdict(report).items() if k != "interval"},
                 "start": iso(report.interval.start), "end": iso(report.interval.end)}
                for report in self.intervals
            ],
            "repeated_between_intervals": self.repeated,
            "distinct_events": self.distinct,
            "declared_by_usgs": self.declared_total,
            "difference": self.difference,
        }

    def render(self) -> str:
        head = f"Periodo {self.request.start:%Y-%m-%dT%H:%M:%SZ} → {self.request.end:%Y-%m-%dT%H:%M:%SZ} · {self.request.filters.describe()}"
        lines = [head, f"{'Intervalo':<45}{'Declarados':>11}{'Recibidos':>11}{'Terremotos':>11}{'Excluidos':>10}{'Publicados':>11}  Fichero"]

        def cell(value: int | None, width: int) -> str:
            return f"{'—' if value is None else value:>{width}}"

        for r in self.intervals:
            label = f"{r.interval.start:%Y-%m-%d %H:%M:%S} → {r.interval.end:%Y-%m-%d %H:%M:%S}"
            lines.append(f"{label:<45}{cell(r.declared, 11)}{cell(r.received, 11)}{cell(r.earthquakes, 11)}"
                         f"{cell(r.excluded, 10)}{cell(r.published, 11)}  {r.file_status}")
        if self.request.dry_run:
            lines.append(f"Prueba sin descarga: {len(self.intervals)} intervalo(s), {sum(r.declared for r in self.intervals)} eventos declarados")
            return "\n".join(lines)
        lines += [
            f"Repetidos entre intervalos: {self.repeated}",
            f"Eventos distintos:      {self.distinct}",
            f"Declarados por USGS:    {self.declared_total}   (recuento del periodo completo al terminar)",
            f"Diferencia:             {self.difference}",
        ]
        return "\n".join(lines)


# ------------------------------------------------------------------------ loader


REUSABLE = """
SELECT e.extraction_id, r.file_path, r.content_sha256
FROM extraction e
JOIN raw_payload r ON r.content_sha256 = e.content_sha256 AND r.encoding = 'file'
WHERE e.source = 'usgs_catalog' AND e.outcome = 'ok' AND e.request_params = $1::jsonb
ORDER BY e.extraction_id DESC
LIMIT 1
"""


class CatalogLoader:
    def __init__(
        self,
        settings: CatalogLoaderSettings,
        pool: asyncpg.Pool,
        producer: AIOKafkaProducer,
        *,
        fetcher: Callable[..., Any] = fetch_async,
        out: Callable[[str], None] = print,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.settings = settings
        self.pool = pool
        self.producer = producer
        self.fetcher = fetcher
        self.out = out
        self.clock = clock
        self.base = settings.usgs.catalog_url
        self.data_dir = Path(settings.data_dir)
        self.catalog_dir = self.data_dir / CATALOG_SUBDIR
        self.seen: set[str] = set()

    # -- requests ---------------------------------------------------------------
    async def _record(self, result: FetchResult, request: LoadRequest, *, endpoint: str, params: dict[str, Any],
                      interval: Interval, counts: Counts | None = None, fingerprint: str | None = None,
                      extra_detail: str | None = None, body_to_keep: bytes | None = None) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                extraction_id = await provenance.record_extraction(
                    conn, result, source=SOURCE, purpose=request.purpose, counts=counts, fingerprint=fingerprint,
                    request_params=recorded_params(endpoint, params), window=(interval.start, interval.end),
                    extra_detail=extra_detail,
                )
                if body_to_keep is not None and fingerprint:
                    await provenance.store_body(conn, fingerprint, body_to_keep, seen_at=result.requested_at)
        return extraction_id

    async def _count(self, interval: Interval, request: LoadRequest) -> tuple[int, int]:
        params = request.filters.count_params(interval)
        result = await self.fetcher(f"{self.base}/count", params, settings=self.settings.usgs, expect="count")
        declared = result.payload["count"] if result.outcome == "ok" else None
        await self._record(result, request, endpoint="count", params=params, interval=interval,
                           counts=Counts(record=declared) if declared is not None else None)
        if declared is None:
            raise LoadError(f"count of {interval.label()} failed: {result.outcome} {result.error_detail or ''}".strip())
        return declared, int(result.payload.get("maxAllowed", 20_000))

    async def _reusable(self, params: dict[str, Any]) -> tuple[int, Path, str] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(REUSABLE, json.dumps(recorded_params("query", params), sort_keys=True))
        if row is None:
            return None
        path = self.data_dir / row["file_path"]
        if not path.is_file() or file_fingerprint(path) != row["content_sha256"]:
            return None   # missing or altered: download again (edge case of the spec)
        return row["extraction_id"], path, row["content_sha256"]

    def _write_file(self, name: str, body: bytes) -> Path:
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        target = self.catalog_dir / name
        temporary = self.catalog_dir / f".{name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        temporary.write_bytes(body)
        os.replace(temporary, target)   # never a half-written file, even with two loads at once
        return target

    def _store_download(self, interval: Interval, filters: Filters, body: bytes) -> tuple[Path, str]:
        """Write an immutable file named after its own fingerprint; returns (path, fingerprint)."""
        fingerprint = bytes_fingerprint(body)
        path = self._write_file(file_name(interval, filters, fingerprint), body)
        return path, fingerprint

    # -- one interval -------------------------------------------------------------
    async def _load_interval(self, interval: Interval, declared: int, request: LoadRequest, summary: Summary) -> None:
        if request.dry_run:
            summary.intervals.append(IntervalReport(interval, declared, file_status="prueba"))
            return
        params = request.filters.query_params(interval)
        reused = None if request.refresh else await self._reusable(params)
        report = IntervalReport(interval, declared)
        if reused is not None:
            extraction_id, path, _ = reused
            features = json.loads(path.read_bytes())["features"]
            report.file_status = "reutilizado"
        else:
            result = await self.fetcher(f"{self.base}/query", params, settings=self.settings.usgs)
            if limit_exceeded(result):
                # The catalog grew past the maximum since /count: record and split again.
                await self._record(result, request, endpoint="query", params=params, interval=interval)
                for part, part_declared in await plan_intervals(interval, lambda i: self._count(i, request)):
                    await self._load_interval(part, part_declared, request, summary)
                return
            if result.outcome != "ok":
                keep = result.body if result.outcome in ("invalid_json", "invalid_structure") else None
                await self._record(result, request, endpoint="query", params=params, interval=interval,
                                   fingerprint=bytes_fingerprint(keep) if keep else None, body_to_keep=keep)
                raise LoadError(f"download of {interval.label()} failed: {result.outcome} {result.error_detail or ''}".strip())
            features = result.payload["features"]
            if len(features) != declared:
                recount, _ = await self._count(interval, request)
                if recount != len(features):
                    await self._record(result, request, endpoint="query", params=params, interval=interval,
                                       extra_detail=f"rejected: received {len(features)} events, declared {declared}, "
                                                    f"recounted {recount}")
                    raise LoadError(f"{interval.label()}: received {len(features)} events but USGS declares {recount}")
                report.declared = declared = recount
            split = classify(features)
            path, fingerprint = self._store_download(interval, request.filters, result.body)
            extraction_id = await self._record(
                result, request, endpoint="query", params=params, interval=interval,
                counts=Counts(split.received, len(split.earthquakes), split.excluded_count),
                fingerprint=fingerprint, extra_detail=split.unidentifiable_detail(),
            )
            async with self.pool.acquire() as conn:
                await provenance.store_file(conn, fingerprint, path.relative_to(self.data_dir).as_posix(),
                                            path.stat().st_size, seen_at=result.requested_at)
            report.file_status = "descargado"

        split = classify(features)
        identifiable = [item.event_id for item in split.earthquakes] + [entry.item.event_id for entry in split.excluded]
        summary.repeated += sum(1 for event_id in set(identifiable) if event_id in self.seen)
        new_earthquakes = [item for item in split.earthquakes if item.event_id not in self.seen]
        self.seen.update(identifiable)

        async with self.pool.acquire() as conn:
            await provenance.record_exclusions(conn, split.excluded, extraction_id)
            outcome = await publish_versions(self.producer, conn, self.settings.kafka.topics.catalog, new_earthquakes,
                                             source=SOURCE, extraction_id=extraction_id)
            if report.file_status == "descargado" or outcome.published:
                await provenance.set_published_count(conn, extraction_id, outcome.published)
        report.received, report.earthquakes = split.received, len(split.earthquakes)
        report.excluded, report.published = split.excluded_count, outcome.published
        summary.intervals.append(report)
        self.out(f"{interval.label()}: declared {report.declared}, received {report.received}, "
                 f"published {report.published} ({report.file_status})")
        if outcome.error is not None:
            raise LoadError(f"Kafka refused a message while publishing {interval.label()}: {outcome.error}")

    # -- whole period ---------------------------------------------------------------
    async def run(self, request: LoadRequest) -> Summary:
        summary = Summary(request)
        for month in month_intervals(request.start, request.end):
            for part, declared in await plan_intervals(month, lambda i: self._count(i, request)):
                await self._load_interval(part, declared, request, summary)
        summary.distinct = len(self.seen)
        if not request.dry_run:
            summary.declared_total, _ = await self._count(Interval(request.start, request.end), request)
            summary.finished_at = self.clock()
            self.catalog_dir.mkdir(parents=True, exist_ok=True)
            stamp = summary.finished_at.strftime("%Y%m%dT%H%M%SZ")
            self._write_file(f"summary-{stamp}-{uuid.uuid4().hex[:6]}.json",
                             json.dumps(summary.to_json(), indent=2, ensure_ascii=False).encode("utf-8"))
        self.out(summary.render())
        return summary


# --------------------------------------------------------------------- command


async def _run(settings: CatalogLoaderSettings, request: LoadRequest) -> int:
    await retry(lambda: ensure_topics(settings.kafka), description="creating Kafka topics", log=logger)
    pool = await create_pool(settings.database, "core", application_name="catalog-loader", max_size=2)
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers, acks="all")
    await retry(producer.start, description="connecting to Kafka", log=logger)
    try:
        if request.list_gaps:
            from .gaps import report_gaps   # spec 003, US4

            return await report_gaps(settings, pool, print)
        summary = await CatalogLoader(settings, pool, producer).run(request)
        return summary.exit_code
    except (LoadError, IntervalTooLarge) as exc:
        print(f"ERROR: {exc}\nWhat was completed is kept; run the same command again to continue.", file=sys.stderr)
        return EXIT_ERROR
    finally:
        await producer.stop()
        await pool.close()


def main(argv: list[str] | None = None) -> int:
    try:
        request = parse_request(sys.argv[1:] if argv is None else argv, datetime.now(timezone.utc))
    except UsageError as exc:
        print(f"catalog-loader: {exc}", file=sys.stderr)
        return EXIT_USAGE
    configure("catalog-loader")
    return asyncio.run(_run(load_settings(), request))


if __name__ == "__main__":
    sys.exit(main())
