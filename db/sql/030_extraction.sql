-- Provenance: every request made to USGS and the distinct raw bodies obtained.

-- One row per request to the live feed or the historical catalog,
-- kept forever (it is small).
CREATE TABLE core.extraction (
    extraction_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source               text NOT NULL CHECK (source IN ('usgs_feed', 'usgs_catalog')),
    purpose              text NOT NULL CHECK (purpose IN ('live', 'historical_load', 'gap_recovery', 'replay_selection')),
    request_url          text NOT NULL,
    request_params       jsonb,                      -- catalog interval, minimum magnitude, event type
    window_start         timestamptz,
    window_end           timestamptz,
    requested_at         timestamptz NOT NULL,
    duration_ms          integer CHECK (duration_ms >= 0),   -- total latency, retries included
    attempt_count        smallint NOT NULL DEFAULT 1 CHECK (attempt_count >= 1),
    http_status          integer,
    outcome              text NOT NULL CHECK (outcome IN ('ok', 'not_modified', 'http_error', 'timeout', 'invalid_json', 'invalid_structure')),
    error_detail         text,
    source_generated_at  timestamptz,                -- metadata.generated of the response
    record_count         integer CHECK (record_count >= 0),
    earthquake_count     integer CHECK (earthquake_count >= 0),
    excluded_count       integer CHECK (excluded_count >= 0),
    published_count      integer CHECK (published_count >= 0),
    content_sha256       text,                       -- fingerprint of the feature collection, not of the headers
    CHECK (window_end IS NULL OR window_start IS NULL OR window_end > window_start)
);

-- One row per distinct content. Feed bodies are stored compressed and purged
-- after RAW_PAYLOAD_RETENTION_DAYS; catalog downloads stay as files in data/.
CREATE TABLE core.raw_payload (
    content_sha256  text PRIMARY KEY,
    encoding        text NOT NULL CHECK (encoding IN ('gzip', 'file')),
    body            bytea,
    file_path       text,                            -- path under data/ for catalog files
    byte_size       integer NOT NULL CHECK (byte_size >= 0),   -- uncompressed size
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    CHECK (body IS NOT NULL OR file_path IS NOT NULL),
    CHECK (last_seen_at >= first_seen_at)
);
