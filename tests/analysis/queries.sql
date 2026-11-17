-- Reproducible queries behind the conclusions of docs/report.md (spec 008, US1).
-- Read-only. Real data only: schema core, never replay or bench.
--
-- Run (Git Bash, values expand inside the container):
--   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < tests/analysis/queries.sql
--
-- Common filter F ("real, earthquake, not synthetic"): core.event_current only holds earthquakes
-- (other types go to core.excluded_event) and the synthetic scale/test cases have identifiers
-- starting with 'synthetic-'. All periods are UTC, start inclusive, end exclusive.

\echo '== Q0 population by year, magnitude >= 4, real =='
SELECT extract(year FROM event_time AT TIME ZONE 'UTC')::int AS year,
       count(*)                                              AS events,
       count(*) FILTER (WHERE magnitude IS NULL)             AS null_magnitude,
       count(*) FILTER (WHERE depth_km IS NULL)              AS null_depth
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%'
GROUP BY 1 ORDER BY 1;

\echo '== Q1 magnitude coverage: all events vs magnitude >= 4, 2025 (catalog only has >= 4) =='
SELECT count(*) AS events_2025, count(*) FILTER (WHERE magnitude >= 4) AS events_2025_m4,
       min(magnitude) AS min_magnitude
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%'
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00';

\echo '== Q2 split by country, 2025, magnitude >= 4 (NULL = Sin pais asignado) =='
WITH f AS (
  SELECT e.country_id, c.name_es AS country_name
  FROM core.event_current e LEFT JOIN core.dim_country c USING (country_id)
  WHERE e.event_id NOT LIKE 'synthetic-%' AND e.magnitude >= 4
    AND e.event_time >= '2025-01-01+00' AND e.event_time < '2026-01-01+00'
)
SELECT coalesce(country_name, 'Sin pais asignado') AS country, count(*) AS events,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM f GROUP BY country_id, country_name ORDER BY events DESC LIMIT 12;

\echo '== Q2b share of events with no country, by magnitude band, 2025 =='
SELECT floor(magnitude)::int AS mag_from,
       count(*) AS events,
       count(*) FILTER (WHERE country_id IS NULL) AS no_country,
       round(100.0 * count(*) FILTER (WHERE country_id IS NULL) / count(*), 1) AS pct_no_country
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
GROUP BY 1 ORDER BY 1;

\echo '== Q3 equivalent comparison: complete UTC day 2026-11-16 vs 2025 daily mean, magnitude >= 4 =='
WITH days AS (
  SELECT d::date AS day FROM generate_series('2025-01-01'::date, '2025-12-31'::date, '1 day') d
), per_day AS (
  SELECT (event_time AT TIME ZONE 'UTC')::date AS day, count(*) AS n
  FROM core.event_current
  WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
    AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
  GROUP BY 1
)
SELECT count(*)                                     AS baseline_days,
       count(*) FILTER (WHERE coalesce(n,0) = 0)    AS days_with_zero_events,
       sum(coalesce(n,0))                           AS baseline_events,
       round(avg(coalesce(n,0)), 2)                 AS daily_mean_with_zero_days,
       round(avg(n), 2)                             AS daily_mean_without_zero_days
FROM days LEFT JOIN per_day USING (day);

\echo '== Q3b recent periods, magnitude >= 4, real =='
SELECT 'day 2026-11-16 (complete UTC day)' AS period, count(*) AS events
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
  AND event_time >= '2026-11-16+00' AND event_time < '2026-11-17+00'
UNION ALL
SELECT 'catalog 2026-01-01..2026-11-15 (319 days)', count(*)
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
  AND event_time >= '2026-01-01+00' AND event_time < '2026-11-15+00';

\echo '== Q3c NON-equivalent comparison (the trap): all magnitudes, last day vs 2025 M>=4 mean =='
SELECT count(*) AS events_all_magnitudes_2026_11_16,
       count(*) FILTER (WHERE magnitude >= 4) AS events_m4_2026_11_16
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%'
  AND event_time >= '2026-11-16+00' AND event_time < '2026-11-17+00';

\echo '== Q4 hour of day UTC, 2025, magnitude >= 4 =='
SELECT extract(hour FROM event_time AT TIME ZONE 'UTC')::int AS hour_utc, count(*) AS events
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
GROUP BY 1 ORDER BY 1;

\echo '== Q5 depth by subregion, 2025, magnitude >= 4 (km; events without depth counted apart) =='
WITH f AS (
  SELECT coalesce(c.subregion, 'Sin pais asignado') AS subregion, e.depth_km
  FROM core.event_current e LEFT JOIN core.dim_country c USING (country_id)
  WHERE e.event_id NOT LIKE 'synthetic-%' AND e.magnitude >= 4
    AND e.event_time >= '2025-01-01+00' AND e.event_time < '2026-01-01+00'
)
SELECT subregion, count(*) AS events, count(*) FILTER (WHERE depth_km IS NULL) AS no_depth,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY depth_km)::numeric, 1) AS median_depth_km,
       round(100.0 * count(*) FILTER (WHERE depth_km >= 300) / nullif(count(depth_km), 0), 1) AS pct_deep_300
FROM f GROUP BY subregion HAVING count(*) >= 100 ORDER BY events DESC;

\echo '== Q6 magnitude types, 2025 magnitude >= 4 vs live 2026-11-10..2026-11-17 all magnitudes =='
SELECT 'catalog 2025 M>=4' AS sample, coalesce(mag_type, 'ND') AS mag_type, count(*) AS events
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
GROUP BY 2
UNION ALL
SELECT 'live 2026-11-10..17 all M', coalesce(mag_type, 'ND'), count(*)
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%'
  AND event_time >= '2026-11-10+00' AND event_time < '2026-11-17+00'
GROUP BY 2
ORDER BY 1, 3 DESC;

\echo '== Q3d daily counts of magnitude >= 4, real: distribution in 2025 and in the 2026 catalog, and where 2026-11-16 falls =='
WITH days AS (
  SELECT d::date AS day FROM generate_series('2025-01-01'::date, '2026-11-14'::date, '1 day') d
), per_day AS (
  SELECT (event_time AT TIME ZONE 'UTC')::date AS day, count(*) AS n
  FROM core.event_current
  WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
    AND event_time >= '2025-01-01+00' AND event_time < '2026-11-15+00'
  GROUP BY 1
), daily AS (
  SELECT day, coalesce(n, 0) AS n, (day < '2026-01-01') AS in_2025 FROM days LEFT JOIN per_day USING (day)
)
SELECT CASE WHEN in_2025 THEN '2025' ELSE '2026-01-01..2026-11-14' END AS period,
       count(*) AS days, round(avg(n), 2) AS mean, round(stddev_samp(n), 2) AS stddev,
       min(n) AS min, percentile_disc(0.05) WITHIN GROUP (ORDER BY n) AS p05,
       percentile_disc(0.5) WITHIN GROUP (ORDER BY n) AS median,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY n) AS p95, max(n) AS max,
       count(*) FILTER (WHERE n <= 15) AS days_le_15
FROM daily GROUP BY in_2025 ORDER BY 1;

\echo '== Q7 depth fixed at 10 km (USGS placeholder for poorly constrained depth), 2025, magnitude >= 4 =='
SELECT count(*) AS events, count(*) FILTER (WHERE depth_km = 10) AS depth_exactly_10,
       round(100.0 * count(*) FILTER (WHERE depth_km = 10) / count(*), 1) AS pct_depth_10,
       count(*) FILTER (WHERE depth_km < 0) AS negative_depth
FROM core.event_current
WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
  AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00';

\echo '== Q8 hour of day UTC, chi-square against a uniform distribution, 2025, magnitude >= 4 =='
WITH h AS (
  SELECT extract(hour FROM event_time AT TIME ZONE 'UTC')::int AS hr, count(*) AS n
  FROM core.event_current
  WHERE event_id NOT LIKE 'synthetic-%' AND magnitude >= 4
    AND event_time >= '2025-01-01+00' AND event_time < '2026-01-01+00'
  GROUP BY 1
)
SELECT sum(n) AS events, round(avg(n), 1) AS expected_per_hour, min(n) AS min_hour, max(n) AS max_hour,
       round(max(n)::numeric / min(n), 2) AS max_over_min,
       round(sum((n - (SELECT avg(n) FROM h))^2 / (SELECT avg(n) FROM h))::numeric, 1) AS chi2_23_df
FROM h;
