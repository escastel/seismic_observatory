"""Ingestion gaps derived from the feed requests (US4: FR-028 to FR-032, research R10)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from producer.app.gaps import Gap, find_gaps, is_covered, recovery_command, warning_line

MARGIN = timedelta(minutes=60)
H = timedelta(hours=1)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


NOW = utc(2026, 11, 15, 12)


def test_no_requests_means_no_gap() -> None:
    assert find_gaps([], NOW, MARGIN) == []


def test_requests_closer_than_24_hours_leave_no_gap() -> None:
    requests = [NOW - 30 * H, NOW - 7 * H, NOW - H]
    assert find_gaps(requests, NOW, MARGIN) == []


def test_closed_gap_between_two_requests() -> None:
    before, after = utc(2026, 11, 13, 9), utc(2026, 11, 14, 21)          # 36 h apart; 14 h before NOW - H
    (gap,) = find_gaps([before, after, NOW - H], NOW, MARGIN)

    assert gap == Gap(start=before - MARGIN, end=after - 24 * H + MARGIN, last_before=before, next_after=after)
    assert gap.end - gap.start == timedelta(hours=14)


def test_open_gap_when_the_last_request_is_old() -> None:
    last = NOW - 36 * H
    (gap,) = find_gaps([last - H, last], NOW, MARGIN)

    assert gap.start == last - MARGIN
    assert gap.end == NOW - 24 * H + MARGIN
    assert gap.next_after is None


def test_open_gap_needs_more_than_24_hours() -> None:
    assert find_gaps([NOW - 23 * H], NOW, MARGIN) == []


def test_coverage_by_one_or_several_windows() -> None:
    gap = Gap(utc(2026, 11, 10, 8), utc(2026, 11, 10, 22), utc(2026, 11, 10, 9), None)

    assert is_covered(gap, [(utc(2026, 11, 10), utc(2026, 11, 11))])
    assert is_covered(gap, [(utc(2026, 11, 10, 8), utc(2026, 11, 10, 15)), (utc(2026, 11, 10, 15), utc(2026, 11, 10, 22))])
    assert is_covered(gap, [(utc(2026, 11, 10, 12), utc(2026, 11, 10, 23)), (utc(2026, 11, 10, 7), utc(2026, 11, 10, 13))])
    assert not is_covered(gap, [(utc(2026, 11, 10, 8), utc(2026, 11, 10, 15)), (utc(2026, 11, 10, 16), utc(2026, 11, 10, 22))])
    assert not is_covered(gap, [(utc(2026, 11, 10, 9), utc(2026, 11, 10, 22))])
    assert not is_covered(gap, [])


def test_recovery_command_and_warning() -> None:
    gap = Gap(utc(2026, 11, 12, 9), utc(2026, 11, 13, 22), utc(2026, 11, 12, 10), None)

    command = recovery_command(gap)
    assert command == ("docker compose run --rm catalog-loader --purpose gap_recovery "
                       "--start 2026-11-12T09:00:00Z --end 2026-11-13T22:00:00Z")
    assert warning_line(gap) == (
        "Ingestion gap detected: last successful feed request at 2026-11-12T10:00:00Z; "
        "events between 2026-11-12T09:00:00Z and 2026-11-13T22:00:00Z are not covered by the feed. "
        f"Recover with: {command}"
    )


def test_seconds_are_dropped_from_the_bounds() -> None:
    last = utc(2026, 11, 13, 10, 17, 42) + timedelta(microseconds=123)
    (gap,) = find_gaps([last], last + 30 * H, MARGIN)
    assert gap.start.second == 0 and gap.start.microsecond == 0
    assert gap.end.second == 0 and gap.end.microsecond == 0
    assert gap.start <= last - MARGIN and gap.end >= last + 30 * H - 24 * H + MARGIN
