-- Secondary indexes. TEMPLATE: db/sql/apply.sh runs this file once per schema
-- with the psql variable "schema" set to core and to replay.
--
-- Only indexes whose query was at least 2 times faster (median) with
-- 1 000 000 synthetic rows survive (FR-026, FR-027, research.md R11).
-- Measurement: docs/evidence/002/index-benchmark.md, by
-- tests/benchmark/index_benchmark.py. Discarded or measure-only candidates
-- are documented in docs/report.md («Índices»).
-- Primary keys are not repeated here: event_version (event_id, updated_at)
-- already serves the versions of an event (x4859 against a copy without key).

SET search_path = :"schema", core;

-- Time interval, hourly windows and the last 24 hours of the map:
--   WHERE event_time >= $1 AND event_time < $2 ORDER BY event_time DESC
-- Measured x126 (last 24 h) and x2.4 (one month by hour); 21 MiB at 1M rows.
-- A BRIN on event_time was measured as the compact alternative and lost on
-- both queries (x34 and x2.0), so the B-tree stays.
CREATE INDEX event_current_event_time_idx ON event_current (event_time);

-- Country filter over an interval:
--   WHERE country_id = $1 AND event_time >= $2 AND event_time < $3
-- Measured x199; 30 MiB at 1M rows.
CREATE INDEX event_current_country_event_time_idx ON event_current (country_id, event_time);

-- Minimum magnitude over long periods (min_mag):
--   WHERE magnitude >= $1 AND event_time >= $2 AND event_time < $3
-- Measured x40 with a selective filter (M >= 4 is about 0.1 % of the
-- synthetic events); 30 MiB at 1M rows.
CREATE INDEX event_current_magnitude_event_time_idx ON event_current (magnitude, event_time);

-- last_ingestion of the API, only once (core.extraction exists only in core):
--   SELECT max(requested_at) FROM core.extraction
--   WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified')
-- Measured x4936; partial, so failed requests and catalog loads stay out.
SELECT :'schema' = 'core' AS is_core_schema \gset
\if :is_core_schema
CREATE INDEX extraction_last_ok_feed_idx ON core.extraction (requested_at)
    WHERE source = 'usgs_feed' AND outcome IN ('ok', 'not_modified');
\endif

RESET search_path;
