-- Shared dimensions, loaded once when the database is created.

-- One row per Natural Earth Admin 0 entity in the delivered catalog.
-- ADM0_A3 is the Natural Earth identifier, not necessarily an ISO code:
-- the primary key makes the load fail if the catalog ever repeats it.
CREATE TABLE core.dim_country (
    country_id  text PRIMARY KEY,           -- ADM0_A3
    name_es     text NOT NULL,              -- NAME_ES, shown in the dashboard
    admin_name  text NOT NULL,              -- ADMIN
    continent   text NOT NULL,              -- CONTINENT
    subregion   text NOT NULL,              -- SUBREGION
    iso_a3      text                        -- ISO_A3, NULL when Natural Earth says -99
);

-- pg_read_file reads the catalog on the database server, mounted read only
-- at :catalog_path by compose.yaml.
INSERT INTO core.dim_country (country_id, name_es, admin_name, continent, subregion, iso_a3)
SELECT p ->> 'ADM0_A3',
       p ->> 'NAME_ES',
       p ->> 'ADMIN',
       p ->> 'CONTINENT',
       p ->> 'SUBREGION',
       NULLIF(p ->> 'ISO_A3', '-99')
FROM jsonb_array_elements(pg_read_file(:'catalog_path')::jsonb -> 'features') AS f(feature),
     LATERAL (SELECT f.feature -> 'properties' AS p) AS props;

-- One row per UTC day, with no gaps, so daily averages can count days
-- without events. Covers the whole USGS catalog (from 1900) and beyond now.
CREATE TABLE core.dim_date (
    date_id      date PRIMARY KEY,
    year         smallint NOT NULL,
    quarter      smallint NOT NULL,
    month        smallint NOT NULL,
    day          smallint NOT NULL,
    iso_week     smallint NOT NULL,
    iso_dow      smallint NOT NULL,         -- 1 = Monday
    day_of_year  smallint NOT NULL
);

INSERT INTO core.dim_date (date_id, year, quarter, month, day, iso_week, iso_dow, day_of_year)
SELECT d::date,
       extract(year FROM d),
       extract(quarter FROM d),
       extract(month FROM d),
       extract(day FROM d),
       extract(week FROM d),
       extract(isodow FROM d),
       extract(doy FROM d)
FROM generate_series(DATE '1900-01-01', DATE '2035-12-31', INTERVAL '1 day') AS d;
