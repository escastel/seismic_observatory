import os

import pytest

pytest.importorskip("psycopg2")

from consumer.app.persistence import ensure_schema


def test_version_history_schema_is_available() -> None:
    dsn = os.getenv("TEST_DATABASE_DSN")
    if not dsn:
        pytest.skip("TEST_DATABASE_DSN is required for database integration tests")
    ensure_schema(dsn)
