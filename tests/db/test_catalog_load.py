"""Catalog load against the real model with a fake USGS and a fake Kafka (US2: FR-018 to FR-027)."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from common.settings import CatalogLoaderSettings, DatabaseSettings, KafkaSettings, TopicNames, UsgsSettings
from producer.app.catalog_load import (
    EXIT_DIFFERENCE,
    EXIT_OK,
    CatalogLoader,
    LoadError,
    parse_request,
)
from tests.db.async_support import run_with_pool
from tests.support.fake_kafka import FakeProducer
from tests.support.usgs_stub import CATALOG_PATH, PASS, FakeCatalog, FakeUsgs, Reply, feature

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
TWO_MONTHS = ["--start", "2025-01-01", "--end", "2025-03-01"]
QUERY = f"{CATALOG_PATH}/query"
COUNT = f"{CATALOG_PATH}/count"


def events() -> list[dict]:
    """5 earthquakes in January, 3 in February, one blast in each month, one M3 earthquake."""
    jan = [feature(f"J{n}", time=f"2025-01-{n + 10:02d}T00:00:00Z", mag=4.5) for n in range(5)]
    feb = [feature(f"F{n}", time=f"2025-02-{n + 10:02d}T00:00:00Z", mag=4.5) for n in range(3)]
    blasts = [feature("B1", time="2025-01-20T00:00:00Z", mag=4.1, event_type="quarry blast"),
              feature("B2", time="2025-02-20T00:00:00Z", mag=4.1, event_type="explosion")]
    small = [feature("S1", time="2025-01-25T00:00:00Z", mag=3.0)]
    return jan + feb + blasts + small


def settings(usgs: FakeUsgs, data_dir: Path) -> CatalogLoaderSettings:
    return CatalogLoaderSettings(
        database=DatabaseSettings("unused", 5432, "unused", "unused", "unused"),
        kafka=KafkaSettings("unused", TopicNames(), 168),
        usgs=UsgsSettings(None, usgs.catalog_url, timeout_seconds=2, max_attempts=1, user_agent="observatory-test/1.0"),
        gap_margin_minutes=60,
        data_dir=str(data_dir),
    )


def load(test_database, usgs, data_dir, producer, argv=TWO_MONTHS):
    """Run one load; return (exit code, summary or None, captured output)."""
    lines: list[str] = []

    async def body(pool):
        loader = CatalogLoader(settings(usgs, data_dir), pool, producer, out=lines.append, clock=lambda: NOW)
        try:
            summary = await loader.run(parse_request(argv, NOW))
        except LoadError as exc:
            lines.append(str(exc))
            return 1, None
        return summary.exit_code, summary

    code, summary = run_with_pool(test_database, body)
    return code, summary, "\n".join(lines)


def extractions(owner_conn: psycopg.Connection) -> list[dict]:
    cursor = owner_conn.execute("SELECT * FROM core.extraction ORDER BY extraction_id")
    names = [column.name for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def downloads(owner_conn) -> list[dict]:
    return [row for row in extractions(owner_conn) if row["request_params"]["endpoint"] == "query"]


@pytest.fixture
def usgs():
    with FakeUsgs(FakeCatalog(events())) as stub:
        yield stub


def test_two_months_are_counted_downloaded_stored_and_published(test_database, owner_conn, usgs, tmp_path) -> None:
    producer = FakeProducer()

    code, summary, output = load(test_database, usgs, tmp_path, producer)

    assert code == EXIT_OK
    counts = [row for row in extractions(owner_conn) if row["request_params"]["endpoint"] == "count"]
    assert [row["record_count"] for row in counts] == [5, 3, 8]          # two months and the final total
    jan, feb = downloads(owner_conn)
    assert (jan["source"], jan["purpose"], jan["outcome"]) == ("usgs_catalog", "historical_load", "ok")
    assert (jan["window_start"], jan["window_end"]) == (datetime(2025, 1, 1, tzinfo=timezone.utc),
                                                        datetime(2025, 2, 1, tzinfo=timezone.utc))
    assert jan["request_params"] == {"endpoint": "query", "format": "geojson", "starttime": "2025-01-01T00:00:00Z",
                                     "endtime": "2025-02-01T00:00:00Z", "minmagnitude": 4,
                                     "eventtype": "earthquake", "orderby": "time-asc"}
    assert (jan["record_count"], jan["earthquake_count"], jan["excluded_count"], jan["published_count"]) == (5, 5, 0, 5)
    assert (feb["record_count"], feb["published_count"]) == (3, 3)

    files = sorted((tmp_path / "usgs" / "catalog").glob("*.geojson"))
    assert [path.name[:-len("_123456789abc.geojson")] for path in files] == [
        "2025-01-01T000000Z_2025-02-01T000000Z_m4_earthquake",
        "2025-02-01T000000Z_2025-03-01T000000Z_m4_earthquake",
    ]
    for path in files:   # the name carries the first 12 hex digits of its own fingerprint
        assert path.stem.endswith(hashlib.sha256(path.read_bytes()).hexdigest()[:12])
    stored = dict(owner_conn.execute(
        "SELECT file_path, content_sha256 FROM core.raw_payload WHERE encoding = 'file' AND body IS NULL").fetchall())
    for path in files:
        relative = f"usgs/catalog/{path.name}"
        assert stored[relative] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert jan["content_sha256"] == stored["usgs/catalog/" + files[0].name]
    assert json.loads(files[0].read_bytes())["features"][0]["id"] == "J0"     # unmodified USGS answer

    assert sorted(producer.keys("earthquakes.catalog")) == ["F0", "F1", "F2", "J0", "J1", "J2", "J3", "J4"]
    assert {message.value["source"] for message in producer.sent} == {"usgs_catalog"}
    assert {message.value["mode"] for message in producer.sent} == {"live"}
    assert (summary.distinct, summary.declared_total, summary.difference, summary.repeated) == (8, 8, 0, 0)
    assert "Diferencia:             0" in output


def test_month_over_the_maximum_is_split_and_never_limited(test_database, owner_conn, tmp_path) -> None:
    with FakeUsgs(FakeCatalog(events(), max_allowed=3)) as usgs:
        code, summary, _ = load(test_database, usgs, tmp_path, FakeProducer())
        queries = usgs.requests_to("/query")

    assert code == EXIT_OK
    assert all("limit" not in request.params for request in queries)
    assert all(report.declared <= 3 for report in summary.intervals)
    assert len(summary.intervals) > 2
    assert summary.distinct == 8


def test_event_in_two_intervals_is_published_once(test_database, tmp_path) -> None:
    boundary = feature("EDGE", time="2025-02-01T00:00:00Z", mag=5.0)
    with FakeUsgs(FakeCatalog(events() + [boundary], inclusive_end=True)) as usgs:
        producer = FakeProducer()
        code, summary, _ = load(test_database, usgs, tmp_path, producer)

    assert producer.keys().count("EDGE") == 1
    assert summary.repeated == 1
    assert summary.distinct == 9
    assert code == EXIT_OK      # the final count with the same inclusive bounds is 9 as well


def test_download_with_fewer_events_than_declared_is_rejected(test_database, owner_conn, usgs, tmp_path) -> None:
    usgs.catalog.query_filter = lambda matching: matching[:-1]

    code, _, output = load(test_database, usgs, tmp_path, FakeProducer())

    assert code == 1
    assert "declares" in output
    assert not list((tmp_path / "usgs" / "catalog").glob("*.geojson"))
    rejected = downloads(owner_conn)[0]
    assert "rejected" in rejected["error_detail"] and rejected["content_sha256"] is None


def test_second_run_downloads_and_publishes_nothing(test_database, owner_conn, usgs, tmp_path) -> None:
    load(test_database, usgs, tmp_path, FakeProducer())
    queries_before = len(usgs.requests_to("/query"))
    events_before = owner_conn.execute("SELECT count(*) FROM core.publish_state").fetchone()[0]

    producer = FakeProducer()
    code, summary, _ = load(test_database, usgs, tmp_path, producer)

    assert code == EXIT_OK
    assert len(usgs.requests_to("/query")) == queries_before
    assert producer.sent == []
    assert {report.file_status for report in summary.intervals} == {"reutilizado"}
    assert owner_conn.execute("SELECT count(*) FROM core.publish_state").fetchone()[0] == events_before


def test_interrupted_load_continues_where_it_stopped(test_database, owner_conn, usgs, tmp_path) -> None:
    usgs.script(QUERY, PASS, Reply.text("busy", status=503), PASS)

    first, _, _ = load(test_database, usgs, tmp_path, FakeProducer())
    assert first == 1

    producer = FakeProducer()
    second, summary, _ = load(test_database, usgs, tmp_path, producer)

    assert second == EXIT_OK
    assert [report.file_status for report in summary.intervals] == ["reutilizado", "descargado"]
    assert sorted(producer.keys()) == ["F0", "F1", "F2"]
    assert len(usgs.requests_to("/query")) == 3
    assert owner_conn.execute("SELECT count(*) FROM core.publish_state").fetchone()[0] == 8


def test_altered_file_is_downloaded_again(test_database, owner_conn, usgs, tmp_path) -> None:
    load(test_database, usgs, tmp_path, FakeProducer())
    path = next((tmp_path / "usgs" / "catalog").glob("2025-01-01*.geojson"))
    path.write_bytes(path.read_bytes().replace(b'"J0"', b'"J9"'))

    _, summary, _ = load(test_database, usgs, tmp_path, FakeProducer())

    assert [report.file_status for report in summary.intervals] == ["descargado", "reutilizado"]
    newest = downloads(owner_conn)[-1]
    (relative,) = owner_conn.execute(
        "SELECT file_path FROM core.raw_payload WHERE content_sha256 = %s", (newest["content_sha256"],)).fetchone()
    fresh = tmp_path / relative
    assert fresh != path and b'"J0"' in fresh.read_bytes()
    assert hashlib.sha256(fresh.read_bytes()).hexdigest() == newest["content_sha256"]


def test_refresh_downloads_again(test_database, usgs, tmp_path) -> None:
    load(test_database, usgs, tmp_path, FakeProducer())
    _, summary, _ = load(test_database, usgs, tmp_path, FakeProducer(), TWO_MONTHS + ["--refresh"])
    assert [report.file_status for report in summary.intervals] == ["descargado", "descargado"]


def test_dry_run_only_counts(test_database, owner_conn, usgs, tmp_path) -> None:
    producer = FakeProducer()

    code, summary, output = load(test_database, usgs, tmp_path, producer, TWO_MONTHS + ["--dry-run"])

    assert code == EXIT_OK
    assert [report.declared for report in summary.intervals] == [5, 3]
    assert usgs.requests_to("/query") == []
    assert producer.sent == []
    assert not (tmp_path / "usgs").exists()
    assert {row["request_params"]["endpoint"] for row in extractions(owner_conn)} == {"count"}
    assert "Prueba sin descarga" in output


def test_difference_with_the_final_total_gives_exit_code_3(test_database, usgs, tmp_path) -> None:
    usgs.script(COUNT, PASS, PASS, Reply.json({"count": 9, "maxAllowed": 20000}))

    code, summary, output = load(test_database, usgs, tmp_path, FakeProducer())

    assert code == EXIT_DIFFERENCE
    assert (summary.declared_total, summary.difference) == (9, -1)
    assert "Diferencia:             -1" in output


def test_other_types_are_kept_as_exclusions(test_database, owner_conn, usgs, tmp_path) -> None:
    producer = FakeProducer()

    load(test_database, usgs, tmp_path, producer, TWO_MONTHS + ["--all-types"])

    rows = owner_conn.execute(
        "SELECT x.event_id, x.event_type, e.source FROM core.excluded_event x "
        "JOIN core.extraction e USING (extraction_id) ORDER BY 1").fetchall()
    assert rows == [("B1", "quarry blast", "usgs_catalog"), ("B2", "explosion", "usgs_catalog")]
    assert "B1" not in producer.keys()


def test_summary_file(test_database, usgs, tmp_path) -> None:
    load(test_database, usgs, tmp_path, FakeProducer())

    (path,) = (tmp_path / "usgs" / "catalog").glob("summary-*.json")
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["period"] == {"start": "2025-01-01T00:00:00Z", "end": "2025-03-01T00:00:00Z"}
    assert summary["filters"] == {"min_magnitude": 4.0, "event_type": "earthquake"}
    assert [interval["declared"] for interval in summary["intervals"]] == [5, 3]
    assert (summary["repeated_between_intervals"], summary["distinct_events"], summary["declared_by_usgs"],
            summary["difference"]) == (0, 8, 8, 0)


def test_failed_count_is_recorded(test_database, owner_conn, usgs, tmp_path) -> None:
    usgs.script(COUNT, Reply.text("busy", status=503))

    code, _, _ = load(test_database, usgs, tmp_path, FakeProducer())

    assert code == 1
    (row,) = extractions(owner_conn)
    assert (row["outcome"], row["http_status"], row["attempt_count"]) == ("http_error", 503, 1)
    assert "503" in row["error_detail"]


def test_unreadable_download_is_kept_and_recorded(test_database, owner_conn, usgs, tmp_path) -> None:
    usgs.script(QUERY, Reply.text("<html>maintenance</html>"))

    code, _, _ = load(test_database, usgs, tmp_path, FakeProducer())

    assert code == 1
    row = downloads(owner_conn)[0]
    assert row["outcome"] == "invalid_json"
    (encoding, body), = owner_conn.execute(
        "SELECT encoding, body FROM core.raw_payload WHERE content_sha256 = %s", (row["content_sha256"],)).fetchall()
    assert encoding == "gzip" and gzip.decompress(body) == b"<html>maintenance</html>"
    assert not list((tmp_path / "usgs" / "catalog").glob("*.geojson"))


def test_older_catalog_version_than_the_feed_one_is_not_published(test_database, owner_conn, usgs, tmp_path) -> None:
    owner_conn.execute("INSERT INTO core.publish_state (event_id, updated_at) VALUES ('J0', '2026-01-01T00:00:00Z')")
    producer = FakeProducer()

    load(test_database, usgs, tmp_path, producer)

    assert "J0" not in producer.keys()
    assert owner_conn.execute("SELECT updated_at FROM core.publish_state WHERE event_id = 'J0'").fetchone()[0] == \
        datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert downloads(owner_conn)[0]["published_count"] == 4


def test_two_simultaneous_loads(test_database, owner_conn, usgs, tmp_path) -> None:
    producers = [FakeProducer(), FakeProducer()]

    async def body(pool):
        loaders = [CatalogLoader(settings(usgs, tmp_path), pool, producer, out=lambda line: None, clock=lambda: NOW)
                   for producer in producers]
        return await asyncio.gather(*(loader.run(parse_request(TWO_MONTHS, NOW)) for loader in loaders))

    summaries = run_with_pool(test_database, body)

    assert [summary.exit_code for summary in summaries] == [EXIT_OK, EXIT_OK]
    for path in (tmp_path / "usgs" / "catalog").glob("*.geojson"):
        stored = owner_conn.execute(
            "SELECT content_sha256 FROM core.raw_payload WHERE file_path = %s", (f"usgs/catalog/{path.name}",)).fetchone()
        assert stored[0] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not list((tmp_path / "usgs" / "catalog").glob("*.tmp"))
    states = owner_conn.execute("SELECT event_id, count(*) FROM core.publish_state GROUP BY 1").fetchall()
    assert len(states) == 8 and all(n == 1 for _, n in states)
    published = {key for producer in producers for key in producer.keys()}
    assert published == {"J0", "J1", "J2", "J3", "J4", "F0", "F1", "F2"}
