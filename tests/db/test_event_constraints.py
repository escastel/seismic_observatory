"""What the event tables accept and reject (FR-006, FR-007, FR-008, FR-010)."""

from __future__ import annotations

import math
from dataclasses import replace

import psycopg
import pytest

from tests.db.helpers import Version, apply_version, utc

BASE = Version("E1", utc("2026-11-14 10:05"))


def test_missing_optional_attributes_are_kept_as_null(writer_conn: psycopg.Connection) -> None:
    version = replace(BASE, magnitude=None, mag_type=None, depth_km=None, place=None, country_id=None)
    assert apply_version(writer_conn, version) == "new"

    row = writer_conn.execute(
        "SELECT magnitude, mag_type, depth_km, place, country_id FROM event_current"
    ).fetchone()
    assert row == (None, None, None, None, None)


def test_negative_magnitude_and_depth_are_accepted(writer_conn: psycopg.Connection) -> None:
    apply_version(writer_conn, replace(BASE, magnitude=-0.6, depth_km=-1.8, quality_flags=["negative_depth"]))

    row = writer_conn.execute("SELECT magnitude, depth_km, quality_flags FROM event_current").fetchone()
    assert row == (-0.6, -1.8, ["negative_depth"])


@pytest.mark.parametrize("longitude", [-180.0001, 180.0001])
def test_longitude_out_of_range_is_rejected(writer_conn: psycopg.Connection, longitude: float) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        apply_version(writer_conn, replace(BASE, longitude=longitude))


@pytest.mark.parametrize("latitude", [-90.0001, 90.0001])
def test_latitude_out_of_range_is_rejected(writer_conn: psycopg.Connection, latitude: float) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        apply_version(writer_conn, replace(BASE, latitude=latitude))


def test_range_limits_are_inclusive(writer_conn: psycopg.Connection) -> None:
    apply_version(writer_conn, replace(BASE, event_id="E1", longitude=-180.0, latitude=-90.0))
    apply_version(writer_conn, replace(BASE, event_id="E2", longitude=180.0, latitude=90.0))


@pytest.mark.parametrize("attribute", ["magnitude", "depth_km", "longitude", "latitude"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf], ids=["nan", "inf", "-inf"])
def test_non_finite_numbers_are_rejected(writer_conn: psycopg.Connection, attribute: str, value: float) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        apply_version(writer_conn, replace(BASE, **{attribute: value}))
    assert writer_conn.execute("SELECT count(*) FROM event_version").fetchone()[0] == 0


def test_unknown_source_is_rejected(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        apply_version(writer_conn, replace(BASE, source="emsc"))


def test_unknown_country_is_rejected(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        apply_version(writer_conn, replace(BASE, country_id="XXX"))


def test_event_date_is_the_utc_day_of_the_event_time(writer_conn: psycopg.Connection) -> None:
    # 00:30 in Madrid summer time is still the previous day in UTC.
    apply_version(writer_conn, replace(BASE, event_time=utc("2026-10-28 00:30:00+02:00")))
    assert str(writer_conn.execute("SELECT event_date FROM event_current").fetchone()[0]) == "2026-10-27"


def test_event_date_follows_a_revised_event_time(writer_conn: psycopg.Connection) -> None:
    apply_version(writer_conn, replace(BASE, event_time=utc("2026-10-27 23:59")))
    apply_version(writer_conn, replace(BASE, updated_at=utc("2026-11-14 10:09"), event_time=utc("2026-10-28 00:01")))
    assert str(writer_conn.execute("SELECT event_date FROM event_current").fetchone()[0]) == "2026-10-28"


def test_event_date_cannot_be_written_directly(owner_conn: psycopg.Connection) -> None:
    apply_version(owner_conn, BASE)
    with pytest.raises(psycopg.errors.GeneratedAlways):
        owner_conn.execute("UPDATE event_current SET event_date = '2000-01-01'")


def test_core_rejects_a_replay_timestamp(writer_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        apply_version(writer_conn, BASE, replayed_at=utc("2026-11-14 12:00"))


def test_replay_requires_a_replay_timestamp(connect) -> None:
    replay = connect("writer", search_path="replay, core")
    with pytest.raises(psycopg.errors.NotNullViolation):
        apply_version(replay, BASE)

    assert apply_version(replay, BASE, replayed_at=utc("2026-11-14 12:00")) == "new"
