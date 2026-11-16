"""Control and status files for a historical replay (data-model.md sections 4 and 5)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTROL_FILE = "control.json"
STATUS_FILE = "status.json"

COMMANDS = ("pause", "resume", "stop")
STATES = ("running", "paused", "stopped", "finished", "failed")
STATUS_FIELDS = (
    "run",
    "state",
    "total",
    "sent",
    "remaining",
    "rate_target",
    "speedup",
    "started_at",
    "updated_at",
    "extraction_id",
    "error",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    for attempt in range(50):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return None
        except PermissionError:
            # Windows: the file is momentarily locked by a concurrent os.replace.
            if attempt == 49:
                raise
            time.sleep(0.005)
    return None


def _replace(src: str, dst: Path) -> None:
    for attempt in range(50):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            # Windows: a reader holds the destination open for a moment.
            if attempt == 49:
                raise
            time.sleep(0.005)


def write_control(directory: str | Path, command: str) -> dict[str, Any]:
    """Write a control order; an unknown command raises ValueError."""
    if command not in COMMANDS:
        raise ValueError(
            f"Orden de control desconocida: {command!r}. Valores admitidos: {', '.join(COMMANDS)}."
        )
    payload = {"command": command, "requested_at": _now()}
    _atomic_write(Path(directory) / CONTROL_FILE, payload)
    return payload


def read_control(directory: str | Path) -> dict[str, Any] | None:
    """Return the pending order or None."""
    return _read_json(Path(directory) / CONTROL_FILE)


def consume_control(directory: str | Path) -> dict[str, Any] | None:
    """Read the pending order and delete the file."""
    path = Path(directory) / CONTROL_FILE
    order = _read_json(path)
    if order is not None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return order


def write_status(directory: str | Path, **fields: Any) -> dict[str, Any]:
    """Merge fields into status.json atomically; updated_at is set unless given."""
    unknown = sorted(set(fields) - set(STATUS_FIELDS))
    if unknown:
        raise ValueError(f"Campos de estado desconocidos: {', '.join(unknown)}.")
    state = fields.get("state")
    if state is not None and state not in STATES:
        raise ValueError(
            f"Estado desconocido: {state!r}. Valores admitidos: {', '.join(STATES)}."
        )
    current = read_status(directory) or {name: None for name in STATUS_FIELDS}
    current.update(fields)
    if "updated_at" not in fields:
        current["updated_at"] = _now()
    _atomic_write(Path(directory) / STATUS_FILE, current)
    return current


def read_status(directory: str | Path) -> dict[str, Any] | None:
    """Return the current status or None."""
    return _read_json(Path(directory) / STATUS_FILE)
