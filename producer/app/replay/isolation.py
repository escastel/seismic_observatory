"""Proof that a replay leaves the real data in schema ``core`` untouched (FR-013, SC-003, R5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg

SNAPSHOT_PATH = Path("data/replay/core-snapshot.json")
EXTRACTION_TABLE = "extraction"
SELECTION_PURPOSE = "replay_selection"

_TABLES_SQL = """
SELECT c.relname
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'core' AND c.relkind IN ('r', 'p')
ORDER BY c.relname
"""


@dataclass(frozen=True)
class TableDifference:
    """One core table whose count or checksum changed (or that appeared or disappeared)."""

    table: str
    before_rows: int | None
    after_rows: int | None
    before_checksum: str | None
    after_checksum: str | None

    def describe(self) -> str:
        return (
            f"core.{self.table}: filas {self.before_rows} -> {self.after_rows}, "
            f"suma {self.before_checksum} -> {self.after_checksum}"
        )


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def take_snapshot(conn: asyncpg.Connection) -> dict[str, Any]:
    """Row count and order-independent checksum for every table of ``core``.

    Returns ``{"tables": {name: {"rows": int, "checksum": str}}, "replay_selection_rows": int}``.
    Checksums are strings so that they survive JSON without losing precision.
    """
    names = [record["relname"] for record in await conn.fetch(_TABLES_SQL)]
    tables: dict[str, dict[str, Any]] = {}
    for name in names:
        where = f" WHERE t.purpose <> '{SELECTION_PURPOSE}'" if name == EXTRACTION_TABLE else ""
        row = await conn.fetchrow(
            "SELECT count(*) AS rows, "  # noqa: S608
            "coalesce(sum(hashtextextended(t::text, 0)::numeric), 0)::text AS checksum "
            f"FROM core.{_quote(name)} AS t{where}"
        )
        tables[name] = {"rows": int(row["rows"]), "checksum": str(row["checksum"])}
    selection_rows = 0
    if EXTRACTION_TABLE in tables:
        selection_rows = int(
            await conn.fetchval(f"SELECT count(*) FROM core.extraction WHERE purpose = '{SELECTION_PURPOSE}'")  # noqa: S608
        )
    return {"tables": tables, "replay_selection_rows": selection_rows}


def compare(snapshot: dict[str, Any], current: dict[str, Any]) -> list[TableDifference]:
    """Differences between two snapshots; empty when isolation held."""
    before, after = snapshot["tables"], current["tables"]
    differences: list[TableDifference] = []
    for table in sorted(set(before) | set(after)):
        old, new = before.get(table), after.get(table)
        if old == new:
            continue
        differences.append(
            TableDifference(
                table,
                old["rows"] if old else None,
                new["rows"] if new else None,
                old["checksum"] if old else None,
                new["checksum"] if new else None,
            )
        )
    return differences


def save(snapshot: dict[str, Any], path: Path = SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
