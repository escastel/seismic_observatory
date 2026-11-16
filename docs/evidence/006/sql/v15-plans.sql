-- V15: planes de las consultas de la API (spec 006) sobre la base local, esquema core.
-- Se ejecuta con: docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < docs/evidence/006/sql/v15-plans.sql
SET search_path = core;
\echo '== Q1 ventana por defecto (24 h), página de 1000'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT f.event_id, f.event_time FROM event_current f LEFT JOIN core.dim_country g ON g.country_id = f.country_id WHERE f.event_time >= now() - interval '24 hours' AND NOT (starts_with(f.event_id,'synthetic-') OR 'synthetic' = ANY(f.quality_flags)) ORDER BY f.event_time DESC, f.event_id ASC LIMIT 1000 OFFSET 0;
\echo '== Q2 año 2025 con min_mag, página de 1000'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT f.event_id FROM event_current f LEFT JOIN core.dim_country g ON g.country_id = f.country_id WHERE f.event_time >= '2025-01-01+00' AND f.event_time < '2026-01-01+00' AND f.magnitude >= 4 AND NOT (starts_with(f.event_id,'synthetic-') OR 'synthetic' = ANY(f.quality_flags)) ORDER BY f.event_time DESC, f.event_id ASC LIMIT 1000 OFFSET 0;
\echo '== Q3 país + periodo (total)'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT count(*) FROM event_current f WHERE f.event_time >= '2025-01-01+00' AND f.event_time < '2026-01-01+00' AND f.country_id = 'JPN' AND NOT (starts_with(f.event_id,'synthetic-') OR 'synthetic' = ANY(f.quality_flags));
\echo '== Q4 solo magnitud (sin periodo), total'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT count(*) FROM event_current f WHERE f.magnitude >= 6 AND NOT (starts_with(f.event_id,'synthetic-') OR 'synthetic' = ANY(f.quality_flags));
\echo '== Q5 estadísticas por hora, año 2025'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT date_bin('1 hour', f.event_time, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS w, count(*) FROM event_current f WHERE f.event_time >= '2025-01-01+00' AND f.event_time < '2026-01-01+00' AND f.magnitude >= 4 AND NOT (starts_with(f.event_id,'synthetic-') OR 'synthetic' = ANY(f.quality_flags)) GROUP BY 1;
\echo '== Q6 última ingesta'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT max(requested_at) FROM core.extraction WHERE source = 'usgs_feed' AND outcome IN ('ok','not_modified');
\echo '== Q7 cuarentena'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT count(*), count(*) FILTER (WHERE reason_codes && ARRAY['geometry_missing']::text[]) FROM quarantine WHERE NOT is_synthetic;
\echo '== Q8 reproducción: página sin periodo'
SET search_path = replay, core;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT f.event_id FROM event_current f ORDER BY f.event_time DESC, f.event_id ASC LIMIT 1000;
SELECT 'filas core' AS dato, count(*)::text FROM core.event_current UNION ALL SELECT 'filas replay', count(*)::text FROM replay.event_current UNION ALL SELECT 'filas extraction', count(*)::text FROM core.extraction;
