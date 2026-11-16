"""Instants before 1970 convert the same way on Windows and Linux.

datetime.fromtimestamp() raises OSError for negative values on Windows, which used to turn a valid
(if old) USGS instant into a quarantine reason there only. Both converters add milliseconds to the
epoch instead.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from consumer.app.rules import _instant
from producer.app.classify import millis_to_utc

CASES = [
    (0, datetime(1970, 1, 1, tzinfo=timezone.utc)),
    (-1, datetime(1969, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc)),
    (-2_208_988_800_000, datetime(1900, 1, 1, tzinfo=timezone.utc)),
    (-2_800_000_000_000, datetime(1881, 4, 9, 14, 13, 20, tzinfo=timezone.utc)),
    (1_735_690_402_650, datetime(2025, 1, 1, 0, 13, 22, 650000, tzinfo=timezone.utc)),
]


@pytest.mark.parametrize(("millis", "expected"), CASES)
def test_consumer_converts_instants_including_pre_1970(millis: int, expected: datetime) -> None:
    assert _instant(millis) == expected


@pytest.mark.parametrize(("millis", "expected"), CASES)
def test_producer_converts_instants_including_pre_1970(millis: int, expected: datetime) -> None:
    assert millis_to_utc(millis) == expected


@pytest.mark.parametrize("value", [1e30, -1e30, float("inf"), float("nan"), True, "x", None])
def test_impossible_instants_are_still_rejected(value) -> None:
    assert _instant(value) is None
    assert millis_to_utc(value) is None
