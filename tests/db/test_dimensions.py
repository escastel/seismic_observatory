"""Reference dimensions loaded by db/sql/020_dimensions.sql (FR-016, FR-017)."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

# Natural Earth entities whose ISO_A3 is -99 in the delivered catalog:
# Norway, France, Northern Cyprus, Somaliland and Kosovo.
ENTITIES_WITHOUT_ISO_CODE = {"NOR", "FRA", "CYN", "SOL", "KOS"}


def test_country_dimension_has_every_catalog_entity(owner_conn: psycopg.Connection) -> None:
    count = owner_conn.execute("SELECT count(*) FROM dim_country").fetchone()[0]
    assert count == 177


def test_minus_99_iso_codes_are_stored_as_null(owner_conn: psycopg.Connection) -> None:
    rows = owner_conn.execute("SELECT country_id FROM dim_country WHERE iso_a3 IS NULL").fetchall()
    assert {row[0] for row in rows} == ENTITIES_WITHOUT_ISO_CODE
    assert owner_conn.execute("SELECT count(*) FROM dim_country WHERE iso_a3 = '-99'").fetchone()[0] == 0


def test_country_mandatory_attributes_are_never_blank(owner_conn: psycopg.Connection) -> None:
    blank = owner_conn.execute(
        """
        SELECT count(*) FROM dim_country
        WHERE btrim(country_id) = '' OR btrim(name_es) = '' OR btrim(admin_name) = ''
           OR btrim(continent) = '' OR btrim(subregion) = ''
        """
    ).fetchone()[0]
    assert blank == 0


def test_known_entities_carry_their_catalog_attributes(owner_conn: psycopg.Connection) -> None:
    row = owner_conn.execute(
        "SELECT name_es, admin_name, continent, subregion, iso_a3 FROM dim_country WHERE country_id = 'ESP'"
    ).fetchone()
    assert row == ("España", "Spain", "Europe", "Southern Europe", "ESP")


def test_repeated_country_identifier_is_rejected(owner_conn: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.UniqueViolation):
        owner_conn.execute(
            "INSERT INTO dim_country (country_id, name_es, admin_name, continent, subregion)"
            " VALUES ('ESP', 'Duplicada', 'Duplicate', 'Europe', 'Southern Europe')"
        )


def test_date_dimension_covers_1900_to_2035_without_gaps(owner_conn: psycopg.Connection) -> None:
    first, last, days = owner_conn.execute("SELECT min(date_id), max(date_id), count(*) FROM dim_date").fetchone()
    assert (first, last) == (date(1900, 1, 1), date(2035, 12, 31))
    assert days == 49_673
    assert days == (last - first).days + 1


def test_date_dimension_calendar_attributes(owner_conn: psycopg.Connection) -> None:
    # 2024-02-29 is a leap day, a Thursday, in ISO week 9 and the first quarter.
    row = owner_conn.execute(
        "SELECT year, quarter, month, day, iso_week, iso_dow, day_of_year FROM dim_date WHERE date_id = '2024-02-29'"
    ).fetchone()
    assert row == (2024, 1, 2, 29, 9, 4, 60)
