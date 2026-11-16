"""The rules module and contracts/rules-catalog.md carry exactly the same codes."""

from __future__ import annotations

import re
from pathlib import Path

from consumer.app import rules

DOCUMENT = Path(__file__).resolve().parents[2] / "specs" / "004-consumer-quality" / "contracts" / "rules-catalog.md"
DIMENSIONS = {"Completitud", "Unicidad", "Validez", "Consistencia", "Actualidad", "Exactitud"}
RETIRED = {"magnitude_null", "event_too_old", "future_timestamp", "duplicate_id"}


def documented_codes() -> dict[str, set[str]]:
    """Backticked codes in the first column of each table, by section."""
    sections: dict[str, set[str]] = {}
    current = ""
    for line in DOCUMENT.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].split(" (")[0].strip()
            sections[current] = set()
        elif line.startswith("|") and current:
            first = line.split("|")[1]
            sections[current].update(re.findall(r"`([a-z_]+)`", first))
    return sections


def test_codes_match_the_document_section_by_section() -> None:
    documented = documented_codes()
    by_effect = {
        "quarantine": documented["Cuarentena"],
        "exclusion": documented["Exclusión"],
        "flag": documented["Marcas"],
    }
    for effect, codes in by_effect.items():
        assert codes, effect
        assert {rule.code for rule in rules.CATALOG if rule.effect == effect} == codes


def test_codes_are_unique() -> None:
    codes = [rule.code for rule in rules.CATALOG]
    assert len(codes) == len(set(codes))


def test_every_rule_has_one_of_the_six_dimensions() -> None:
    for rule in rules.CATALOG:
        assert rule.dimension in DIMENSIONS or rule.code == "synthetic", rule
        assert rule.description


def test_retired_rules_are_not_in_the_catalog() -> None:
    assert not RETIRED & {rule.code for rule in rules.CATALOG}
