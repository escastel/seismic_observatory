import os

import pytest

pytest.importorskip("psycopg2")

from producer.app.persistence import ensure_state_table, mark_published, should_publish


def test_publisher_state_rejects_unchanged_versions() -> None:
    dsn = os.getenv("TEST_DATABASE_DSN")
    if not dsn:
        pytest.skip("TEST_DATABASE_DSN is required for database integration tests")
    from datetime import datetime, timezone

    updated = datetime(2025, 1, 1, tzinfo=timezone.utc)
    ensure_state_table(dsn)
    mark_published(dsn, "integration-state", updated)
    assert should_publish(dsn, "integration-state", updated) is False
