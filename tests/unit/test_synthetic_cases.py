"""Every synthetic case lands where its table says when it goes through the rules."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from consumer.app.rules import CATALOG, Accepted, Exclusion, Quarantine, evaluate
from tests.synthetic.cases import BATCH_PREFIX, EXCLUSION, QUARANTINE, build_cases, restart_batch

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
CASES = build_cases(NOW)


@pytest.mark.parametrize("case", CASES, ids=[c.case for c in CASES])
def test_case_lands_on_its_expected_outcome(case) -> None:
    result = evaluate(case.raw(), NOW)
    expected = case.expected_at_rules
    if expected == QUARANTINE:
        assert isinstance(result, Quarantine)
        assert result.reasons == list(case.codes)
    elif expected == EXCLUSION:
        assert isinstance(result, Exclusion)
        assert result.reason_code == case.codes[0]
    else:
        assert isinstance(result, Accepted)
        if case.rules_outcome is None:
            assert tuple(result.flags) == case.codes


@pytest.mark.parametrize("case", CASES, ids=[c.case for c in CASES])
def test_case_is_marked_and_named(case) -> None:
    assert case.event_id == f"synthetic-{case.case}"
    assert b"synthetic" in case.raw()
    if isinstance(case.message, dict):
        assert case.message["synthetic"] is True and case.message["synthetic_case"] == case.case


def test_every_rule_of_the_catalog_has_a_case() -> None:
    covered = {code for c in CASES for code in c.codes}
    missing = {rule.code for rule in CATALOG} - covered - {"ambiguous_country"}
    assert not missing


def test_acceptance_cases_exist() -> None:
    assert {"null_magnitude", "invalid_coordinates", "maritime_event"} <= {c.case for c in CASES}


def test_restart_batch_is_valid_distinct_and_marked() -> None:
    batch = restart_batch(1000, NOW)
    assert len({m["id"] for m in batch}) == 1000
    assert all(m["id"].startswith(BATCH_PREFIX) and m["synthetic"] is True for m in batch)
    results = [evaluate(json.dumps(m).encode(), NOW) for m in batch]
    assert all(isinstance(r, Accepted) and r.flags == ["synthetic"] for r in results)
