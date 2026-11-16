"""Command line of the historical replay (contracts/replay-cli.md).

    docker compose run --rm replay <select|start|snapshot|compare> [options]

Exit codes: 0 correct, 1 usage error, 2 selection rejected, 5 Kafka or
database failure, 6 `compare` found differences in core, 3 no active replay
(pause/resume/stop), 4 a replay is already active (start/reset).
Use `--bbox=-10,30,10,50` for a bbox starting with a minus sign.
All external effects go through `Deps` so the tests can replace them.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common import settings as common_settings
from common.db import create_pool
from common.logging import configure
from common.retry import retry
from common.settings import ReplaySettings, SettingsError
from common.topics import ensure_topics

from . import control, isolation, runner, selection, synthetic
from .runner import ReplayItem
from .selection import BBox, Selection, SelectionRejected

logger = logging.getLogger(__name__)

EXIT_OK, EXIT_USAGE, EXIT_REJECTED, EXIT_FAILURE, EXIT_DIFFERENCES = 0, 1, 2, 5, 6
EXIT_NO_ACTIVE, EXIT_BUSY = 3, 4
CONTROL_COMMANDS = control.COMMANDS
SNAPSHOT_NAME = "core-snapshot.json"


class UsageError(ValueError):
    """Invalid arguments: nothing is read or published (exit code 1)."""


# --------------------------------------------------------------------- arguments


@dataclass(frozen=True)
class Request:
    command: str
    start: datetime | None = None
    end: datetime | None = None
    min_mag: float | None = None
    bbox: BBox | None = None
    rate: float | None = None      # None: REPLAY_DEFAULT_RATE
    speedup: float | None = None
    synthetic: bool = False
    synthetic_only: bool = False


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would call sys.exit
        raise UsageError(message)


def parse_instant(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise UsageError(
            f"fecha ilegible {text!r}: use ISO 8601, por ejemplo 2025-01-01 o 2025-01-01T00:00:00Z"
        ) from exc
    return moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _finite(text: str, option: str, *, positive: bool = False) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise UsageError(f"{option} debe ser un número, no {text!r}") from exc
    if not math.isfinite(value):
        raise UsageError(f"{option} debe ser un número finito, no {text!r}")
    if positive and value <= 0:
        raise UsageError(f"{option} debe ser mayor que cero, no {text!r}")
    return value


def _parse_bbox(text: str) -> BBox:
    parts = [p.strip() for p in text.split(",")]
    try:
        numbers = [float(p) for p in parts]
    except ValueError as exc:
        raise UsageError(f"--bbox debe ser MIN_LON,MIN_LAT,MAX_LON,MAX_LAT con números, no {text!r}") from exc
    try:
        box = selection.validate_bbox(numbers)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    assert box is not None
    return box


def _glue_bbox(argv: list[str]) -> list[str]:
    """`--bbox -10,0,10,5` would be read by argparse as an option: glue it as `--bbox=...`."""
    out: list[str] = []
    skip = False
    for i, token in enumerate(argv):
        if skip:
            skip = False
        elif token == "--bbox" and i + 1 < len(argv):
            out.append(f"--bbox={argv[i + 1]}")
            skip = True
        else:
            out.append(token)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="replay", description="Reproducción histórica del catálogo")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)
    sub.required = True
    for name, help_text in (("select", "ver y registrar la selección sin publicar"), ("start", "reproducir")):
        p = sub.add_parser(name, help=help_text)
        is_start = name == "start"
        p.add_argument("--start", required=not is_start)
        p.add_argument("--end", required=not is_start)
        p.add_argument("--min-mag", required=not is_start)
        p.add_argument("--bbox")
        if is_start:
            p.add_argument("--rate")
            p.add_argument("--speedup")
            p.add_argument("--synthetic", action="store_true")
            p.add_argument("--synthetic-only", action="store_true")
    for name, help_text in (
        ("pause", "pausar la reproducción activa"),
        ("resume", "reanudar la reproducción pausada"),
        ("stop", "detener la reproducción activa"),
        ("status", "mostrar el estado de la reproducción"),
        ("reset", "vaciar las tablas de replay para repetir desde cero"),
    ):
        sub.add_parser(name, help=help_text)
    sub.add_parser("snapshot", help="guardar recuento y suma de cada tabla de core")
    sub.add_parser("compare", help="comparar core con la instantánea")
    return parser


def parse_request(argv: list[str]) -> Request:
    args = build_parser().parse_args(_glue_bbox(list(argv)))
    if args.command in ("snapshot", "compare", "reset", "status", *CONTROL_COMMANDS):
        return Request(args.command)
    only = bool(getattr(args, "synthetic_only", False))
    extra = bool(getattr(args, "synthetic", False))
    rate = _finite(args.rate, "--rate", positive=True) if getattr(args, "rate", None) is not None else None
    speedup = _finite(args.speedup, "--speedup", positive=True) if getattr(args, "speedup", None) is not None else None
    if only:
        given = [o for o, v in (("--start", args.start), ("--end", args.end), ("--min-mag", args.min_mag),
                                ("--bbox", args.bbox)) if v is not None]
        if given:
            raise UsageError(f"--synthetic-only no admite {', '.join(given)}: no hay selección")
        if extra:
            raise UsageError("--synthetic y --synthetic-only son excluyentes")
        return Request("start", rate=rate, speedup=speedup, synthetic_only=True)
    missing = [o for o, v in (("--start", args.start), ("--end", args.end), ("--min-mag", args.min_mag)) if v is None]
    if missing:
        raise UsageError(f"faltan opciones obligatorias: {', '.join(missing)}")
    start, end = parse_instant(args.start), parse_instant(args.end)
    if end <= start:
        raise UsageError(f"el fin ({end:%Y-%m-%dT%H:%M:%SZ}) debe ser posterior al inicio ({start:%Y-%m-%dT%H:%M:%SZ})")
    return Request(
        args.command,
        start,
        end,
        _finite(args.min_mag, "--min-mag"),
        _parse_bbox(args.bbox) if args.bbox is not None else None,
        rate,
        speedup,
        synthetic=extra,
    )


# ------------------------------------------------------------------ dependencies


async def _default_pool(settings: ReplaySettings) -> Any:
    return await create_pool(settings.database, "core", application_name="replay", max_size=2)


def _default_producer(settings: ReplaySettings) -> Any:
    from aiokafka import AIOKafkaProducer

    return AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers, acks="all")


@dataclass
class Deps:
    """Everything with side effects; the tests pass fakes."""

    load_settings: Callable[[], ReplaySettings] = common_settings.replay
    create_pool: Callable[[ReplaySettings], Any] = _default_pool          # async -> pool
    ensure_topics: Callable[[Any], Any] = ensure_topics                   # async (KafkaSettings)
    make_producer: Callable[[ReplaySettings], Any] = _default_producer    # start/stop/send_and_wait
    locate_files: Callable[..., Any] = selection.locate_files             # async
    select_events: Callable[..., Selection] = selection.select_events
    register_selection: Callable[..., Any] = selection.register_selection  # async
    set_published_count: Callable[..., Any] = selection.set_published_count  # async
    make_lock: Callable[[ReplaySettings], Any] = lambda settings: runner.ActiveRunLock(settings.database.dsn())
    run_replay: Callable[..., Any] = runner.run_replay                    # async
    take_snapshot: Callable[..., Any] = isolation.take_snapshot           # async
    out: Callable[[str], None] = print
    err: Callable[[str], None] = field(default=lambda text: print(text, file=sys.stderr))


# ---------------------------------------------------------------------- commands


def _stamp(ms: int | None) -> str:
    if ms is None:
        return "—"
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=ms)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _select(request: Request, settings: ReplaySettings, pool: Any, deps: Deps) -> tuple[Selection, int]:
    assert request.start and request.end and request.min_mag is not None
    async with pool.acquire() as conn:
        files = await deps.locate_files(conn, settings.data_dir, request.start, request.end, request.min_mag)
    chosen = deps.select_events(files, request.start, request.end, request.min_mag, request.bbox)
    async with pool.acquire() as conn:
        extraction_id = await deps.register_selection(conn, chosen)
    deps.out(
        f"Selección registrada: {chosen.count} eventos, primero {_stamp(chosen.first_time_ms)}, "
        f"último {_stamp(chosen.last_time_ms)}, extraction_id {extraction_id}"
    )
    if chosen.without_magnitude_dropped:
        deps.out(f"Aviso: {chosen.without_magnitude_dropped} eventos sin magnitud no cumplen el mínimo y se descartan")
    if chosen.count == 0:
        deps.out("Aviso: la selección está vacía; no hay nada que reproducir")
    return chosen, extraction_id


async def _start(request: Request, settings: ReplaySettings, pool: Any, deps: Deps) -> int:
    lock = deps.make_lock(settings)
    if not await lock.acquire():  # before registering anything
        deps.err("Ya hay una reproducción activa: espere a que termine o ejecute `replay stop`")
        return EXIT_BUSY
    try:
        return await _start_locked(request, settings, pool, deps, lock)
    except runner.RunLockBusy:
        deps.err("Ya hay una reproducción activa: espere a que termine o ejecute `replay stop`")
        return EXIT_BUSY
    finally:
        await lock.release()


async def _start_locked(request: Request, settings: ReplaySettings, pool: Any, deps: Deps, lock: Any) -> int:
    items: list[ReplayItem] = []
    extraction_id: int | None = None
    if not request.synthetic_only:
        chosen, extraction_id = await _select(request, settings, pool, deps)
        items = [ReplayItem(feature) for feature in chosen.features]
    if request.synthetic_only or request.synthetic:
        items = items + synthetic.synthetic_items()
    if not items:
        return EXIT_OK
    control_dir = Path(settings.data_dir) / "replay"
    rate = request.rate if request.rate is not None else settings.default_rate
    await retry(lambda: deps.ensure_topics(settings.kafka), description="creating Kafka topics", log=logger)
    producer = deps.make_producer(settings)
    await retry(producer.start, description="connecting to Kafka", log=logger)
    try:
        sent = await deps.run_replay(
            producer, items, topic=settings.kafka.topics.replay, extraction_id=extraction_id,
            rate=rate, speedup=request.speedup, control_dir=control_dir, lock=lock,
        )
    finally:
        await producer.stop()
    if extraction_id is not None:
        async with pool.acquire() as conn:
            await deps.set_published_count(conn, extraction_id, sent)
    status = control.read_status(control_dir) or {}
    if status.get("state") == "failed" or sent < len(items):
        if status.get("state") == "stopped":
            deps.out(f"Reproducción detenida: {sent} de {len(items)} eventos publicados")
            return EXIT_OK
        deps.err(f"ERROR: fallo de Kafka tras {sent} de {len(items)} eventos: {status.get('error') or 'sin detalle'}")
        return EXIT_FAILURE
    deps.out(f"Reproducción terminada: {sent} eventos publicados")
    return EXIT_OK


def _control(request: Request, settings: ReplaySettings, deps: Deps) -> int:
    control_dir = Path(settings.data_dir) / "replay"
    status = control.read_status(control_dir) or {}
    if status.get("state") not in ("running", "paused"):
        deps.err("No hay ninguna reproducción activa")
        return EXIT_NO_ACTIVE
    control.write_control(control_dir, request.command)
    deps.out(f"Orden enviada: {request.command}")
    return EXIT_OK


def _status(settings: ReplaySettings, deps: Deps) -> int:
    status = control.read_status(Path(settings.data_dir) / "replay")
    if not status:
        deps.out("Sin reproducción: no hay estado registrado")
        return EXIT_OK
    names = {"running": "en marcha", "paused": "en pausa", "stopped": "detenida",
             "finished": "terminada", "failed": "fallida"}
    target = status.get("rate_target")
    speedup = status.get("speedup")
    deps.out(
        f"Estado: {names.get(status.get('state'), status.get('state'))}; enviados {status.get('sent')}; "
        f"restantes {status.get('remaining')}; objetivo {target if target is not None else '—'} eventos/s"
        + (f", aceleración x{speedup:g}" if speedup else "")
    )
    if status.get("error"):
        deps.out(f"Error: {status['error']}")
    return EXIT_OK


async def _reset(settings: ReplaySettings, pool: Any, deps: Deps) -> int:
    lock = deps.make_lock(settings)
    if not await lock.acquire():
        deps.err("Hay una reproducción activa: no se puede ejecutar reset")
        return EXIT_BUSY
    try:
        async with pool.acquire() as conn:
            await conn.execute("SELECT replay.reset()")
    finally:
        await lock.release()
    deps.out("Tablas de replay vaciadas; core no se ha tocado. Vuelva a ejecutar `replay start`")
    return EXIT_OK


def _snapshot_path(settings: ReplaySettings) -> Path:
    return Path(settings.data_dir) / "replay" / SNAPSHOT_NAME


async def _snapshot(settings: ReplaySettings, pool: Any, deps: Deps) -> int:
    async with pool.acquire() as conn:
        current = await deps.take_snapshot(conn)
    path = _snapshot_path(settings)
    isolation.save(current, path)
    deps.out(f"Instantánea de core guardada en {path}: {len(current['tables'])} tablas")
    return EXIT_OK


async def _compare(settings: ReplaySettings, pool: Any, deps: Deps) -> int:
    path = _snapshot_path(settings)
    try:
        before = isolation.load(path)
    except (OSError, ValueError):
        deps.err(f"No hay instantánea en {path}: ejecute antes `replay snapshot`")
        return EXIT_USAGE
    async with pool.acquire() as conn:
        current = await deps.take_snapshot(conn)
    differences = isolation.compare(before, current)
    if not differences:
        deps.out("core idéntico a la instantánea: el aislamiento se mantiene")
        return EXIT_OK
    deps.err(f"core difiere de la instantánea en {len(differences)} tabla(s):")
    for difference in differences:
        deps.err(f"  {difference.describe()}")
    return EXIT_DIFFERENCES


async def run(request: Request, deps: Deps) -> int:
    settings = deps.load_settings()
    if request.command in CONTROL_COMMANDS:
        return _control(request, settings, deps)
    if request.command == "status":
        return _status(settings, deps)
    pool = await deps.create_pool(settings)
    try:
        if request.command == "select":
            await _select(request, settings, pool, deps)
            return EXIT_OK
        if request.command == "start":
            return await _start(request, settings, pool, deps)
        if request.command == "reset":
            return await _reset(settings, pool, deps)
        if request.command == "snapshot":
            return await _snapshot(settings, pool, deps)
        return await _compare(settings, pool, deps)
    finally:
        await pool.close()


def main(argv: list[str], deps: Deps | None = None) -> int:
    deps = deps or Deps()
    try:
        request = parse_request(argv)
    except UsageError as exc:
        deps.err(f"replay: {exc}")
        return EXIT_USAGE
    if deps.load_settings is common_settings.replay:
        configure("replay")
    try:
        return asyncio.run(run(request, deps))
    except SettingsError as exc:
        deps.err(f"replay: configuración inválida: {exc}")
        return EXIT_USAGE
    except SelectionRejected as exc:
        deps.err(f"Selección rechazada: {exc}")
        return EXIT_REJECTED
    except ValueError as exc:
        deps.err(f"replay: {exc}")
        return EXIT_USAGE
    except Exception as exc:  # database or Kafka failure
        deps.err(f"ERROR: fallo de la base o de Kafka: {type(exc).__name__}: {exc}")
        return EXIT_FAILURE
