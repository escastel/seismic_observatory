"""Verification and record of the replay selection (spec 005, T009; research R7, R8)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from producer.app import provenance
from producer.app.catalog import Filters, Interval, file_name, recorded_params
from producer.app.fingerprint import bytes_fingerprint, file_fingerprint
from producer.app.provenance import Counts
from producer.app.replay.selection import (
    SelectionRejected,
    locate_files,
    register_selection,
    select_events,
    set_published_count,
)
from producer.app.usgs import FetchResult
from tests.db.async_support import run_with_conn
from tests.support.usgs_stub import collection, feature

JAN = datetime(2025, 1, 1, tzinfo=timezone.utc)
FEB = datetime(2025, 2, 1, tzinfo=timezone.utc)
MAR = datetime(2025, 3, 1, tzinfo=timezone.utc)
CATALOG_DIR = Path("usgs") / "catalog"


async def load_month(conn, data_dir: Path, interval: Interval, features: list, min_magnitude: float | None = 4.0):
    """Register a catalog load the way catalog_load.py does: file, extraction and raw_payload."""
    filters = Filters(min_magnitude, "earthquake")
    body = json.dumps(collection(features)).encode()
    fingerprint = bytes_fingerprint(body)
    path = data_dir / CATALOG_DIR / file_name(interval, filters, fingerprint)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    result = FetchResult(
        url="https://earthquake.usgs.gov/fdsnws/event/1/query", requested_at=datetime.now(timezone.utc),
        outcome="ok", http_status=200, attempt_count=1, duration_ms=10, body=body, payload=None,
        error_detail=None, last_modified=None,
    )
    extraction_id = await provenance.record_extraction(
        conn, result, source="usgs_catalog", purpose="historical_load",
        counts=Counts(len(features), len(features), 0), fingerprint=fingerprint,
        request_params=recorded_params("query", filters.query_params(interval)),
        window=(interval.start, interval.end),
    )
    await provenance.store_file(conn, fingerprint, path.relative_to(data_dir).as_posix(), len(body))
    return extraction_id, path


def january_features() -> list:
    return [
        feature("a", "2025-01-05T00:00:00Z", mag=5.0),
        feature("b", "2025-01-10T00:00:00Z", mag=4.5),
        feature("c", "2025-01-20T00:00:00Z", mag=None),
    ]


def test_registers_selection_with_parameters_and_count(test_database, owner_conn, tmp_path) -> None:
    async def body(conn):
        await load_month(conn, tmp_path, Interval(JAN, FEB), january_features())
        files = await locate_files(conn, tmp_path, JAN, FEB, 4.0)
        selection = select_events(files, JAN, FEB, 4.0, bbox=(-10, 30, 10, 50))
        extraction_id = await register_selection(conn, selection)
        await set_published_count(conn, extraction_id, selection.count)
        return files, selection, extraction_id

    files, selection, extraction_id = run_with_conn(test_database, body)

    assert len(files) == 1 and selection.count == 2
    row = owner_conn.execute(
        "SELECT source, purpose, request_url, outcome, window_start, window_end, request_params, record_count, "
        "earthquake_count, excluded_count, published_count, content_sha256 FROM core.extraction "
        "WHERE extraction_id = %s",
        (extraction_id,),
    ).fetchone()
    source, purpose, url, outcome, w_start, w_end, params, records, quakes, excluded, published, sha = row
    assert (source, purpose, url, outcome) == ("usgs_catalog", "replay_selection", "local-catalog:data/usgs/catalog", "ok")
    assert (w_start, w_end) == (JAN, FEB)
    assert (records, quakes, excluded, published) == (2, 2, 0, 2)
    assert sha == selection.content_sha256
    assert params["min_magnitude"] == 4.0 and params["bbox"] == [-10, 30, 10, 50]
    assert params["without_magnitude_dropped"] == 1
    assert params["files"] == [{"path": str(files[0]), "sha256": file_fingerprint(files[0])}]
    assert owner_conn.execute("SELECT count(*) FROM core.extraction WHERE purpose = 'replay_selection'").fetchone()[0] == 1


def test_empty_selection_is_registered_with_zero_events(test_database, owner_conn, tmp_path) -> None:
    async def body(conn):
        await load_month(conn, tmp_path, Interval(JAN, FEB), january_features())
        files = await locate_files(conn, tmp_path, JAN, FEB, 6.0)
        selection = select_events(files, JAN, FEB, 6.0)
        return selection, await register_selection(conn, selection)

    selection, extraction_id = run_with_conn(test_database, body)

    assert selection.count == 0
    row = owner_conn.execute(
        "SELECT record_count, earthquake_count, excluded_count FROM core.extraction WHERE extraction_id = %s",
        (extraction_id,),
    ).fetchone()
    assert row == (0, 0, 0)


def test_altered_file_is_rejected_without_registering(test_database, owner_conn, tmp_path) -> None:
    async def body(conn):
        _, path = await load_month(conn, tmp_path, Interval(JAN, FEB), january_features())
        path.write_bytes(path.read_bytes() + b" ")
        with pytest.raises(SelectionRejected, match="alterado") as info:
            await locate_files(conn, tmp_path, JAN, FEB, 4.0)
        return info.value

    error = run_with_conn(test_database, body)

    assert error.exit_code == 2
    assert owner_conn.execute("SELECT count(*) FROM core.extraction WHERE purpose = 'replay_selection'").fetchone()[0] == 0


def test_missing_file_is_rejected(test_database, tmp_path) -> None:
    async def body(conn):
        _, path = await load_month(conn, tmp_path, Interval(JAN, FEB), january_features())
        path.unlink()
        with pytest.raises(SelectionRejected, match="Falta el fichero"):
            await locate_files(conn, tmp_path, JAN, FEB, 4.0)

    run_with_conn(test_database, body)


def test_period_without_coverage_is_rejected(test_database, tmp_path) -> None:
    async def body(conn):
        await load_month(conn, tmp_path, Interval(JAN, FEB), january_features())
        with pytest.raises(SelectionRejected, match="no está cubierto"):
            await locate_files(conn, tmp_path, JAN, MAR, 4.0)
        with pytest.raises(SelectionRejected, match="no está cubierto"):
            await locate_files(conn, tmp_path, datetime(2024, 12, 1, tzinfo=timezone.utc), FEB, 4.0)

    run_with_conn(test_database, body)


def test_two_contiguous_loads_cover_the_period(test_database, tmp_path) -> None:
    async def body(conn):
        await load_month(conn, tmp_path, Interval(JAN, FEB), january_features())
        await load_month(conn, tmp_path, Interval(FEB, MAR), [feature("d", "2025-02-03T00:00:00Z", mag=4.8)])
        return await locate_files(conn, tmp_path, JAN, MAR, 4.0)

    assert len(run_with_conn(test_database, body)) == 2


def test_insufficient_minimum_magnitude_is_rejected(test_database, tmp_path) -> None:
    async def body(conn):
        await load_month(conn, tmp_path, Interval(JAN, FEB), january_features(), min_magnitude=4.0)
        with pytest.raises(SelectionRejected, match="magnitud mínima"):
            await locate_files(conn, tmp_path, JAN, FEB, 3.0)
        return await locate_files(conn, tmp_path, JAN, FEB, 4.0)

    assert len(run_with_conn(test_database, body)) == 1


def test_load_without_magnitude_filter_accepts_any_minimum(test_database, tmp_path) -> None:
    async def body(conn):
        await load_month(conn, tmp_path, Interval(JAN, FEB), january_features(), min_magnitude=None)
        return await locate_files(conn, tmp_path, JAN, FEB, 0.0)

    assert len(run_with_conn(test_database, body)) == 1
