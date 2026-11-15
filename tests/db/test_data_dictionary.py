"""docs/report.md documents exactly the columns that exist (FR-024, principle IX).

The data dictionary is the section «## Diccionario de datos» of the report.
Each table is a «### » heading naming one or more `schema.table` in backticks,
followed by a Markdown table whose first cell lists the column name(s) in
backticks, for example:

    ### `core.event_current`, `replay.event_current`

    | Columna | Tipo | ... |
    |---|---|---|
    | `event_id` | `text` | ... |
    | `magnitude`, `depth_km` | ... |
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import psycopg

REPORT = Path(__file__).resolve().parents[2] / "docs" / "report.md"
SECTION = "## Diccionario de datos"
TABLE_NAME = re.compile(r"`((?:core|replay)\.[a-z_]+)`")
COLUMN_NAME = re.compile(r"`([a-z_][a-z0-9_]*)`")


def documented_columns(text: str) -> dict[str, set[str]]:
    start = text.index(SECTION) + len(SECTION)
    following = text.find("\n## ", start)
    section = text[start : following if following != -1 else len(text)]

    columns: dict[str, set[str]] = defaultdict(set)
    current: list[str] = []
    for line in section.splitlines():
        if line.startswith("### "):
            current = TABLE_NAME.findall(line)
            continue
        if not current or not line.startswith("|") or set(line) <= {"|", "-", ":", " "}:
            continue
        first_cell = line.strip("|").split("|")[0]
        names = COLUMN_NAME.findall(first_cell)
        for table in current:
            columns[table].update(names)
    return dict(columns)


def actual_columns(conn: psycopg.Connection) -> dict[str, set[str]]:
    rows = conn.execute(
        """
        SELECT c.table_schema || '.' || c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t USING (table_schema, table_name)
        WHERE c.table_schema IN ('core', 'replay') AND t.table_type = 'BASE TABLE'
        """
    ).fetchall()
    columns: dict[str, set[str]] = defaultdict(set)
    for table, column in rows:
        columns[table].add(column)
    return dict(columns)


def test_parser_reads_the_documented_format() -> None:
    sample = (
        "## Diccionario de datos\n\n### `core.a_table`, `replay.a_table`\n\n"
        "| Columna | Tipo |\n|---|---|\n| `one` | `text` |\n| `two`, `three` | `int` |\n\n## Otro\n| `ignored` |\n"
    )
    assert documented_columns(sample) == {
        "core.a_table": {"one", "two", "three"},
        "replay.a_table": {"one", "two", "three"},
    }


def test_every_table_of_the_model_is_documented(owner_conn: psycopg.Connection) -> None:
    documented = documented_columns(REPORT.read_text(encoding="utf-8"))
    actual = actual_columns(owner_conn)

    assert sorted(set(actual) - set(documented)) == [], "tables missing from docs/report.md"
    assert sorted(set(documented) - set(actual)) == [], "docs/report.md describes tables that do not exist"


def test_every_column_is_documented_and_nothing_else(owner_conn: psycopg.Connection) -> None:
    documented = documented_columns(REPORT.read_text(encoding="utf-8"))
    actual = actual_columns(owner_conn)

    missing = {table: sorted(cols - documented.get(table, set())) for table, cols in actual.items()}
    extra = {table: sorted(cols - actual.get(table, set())) for table, cols in documented.items()}
    assert {table: cols for table, cols in missing.items() if cols} == {}, "columns missing from docs/report.md"
    assert {table: cols for table, cols in extra.items() if cols} == {}, "docs/report.md describes columns that do not exist"
