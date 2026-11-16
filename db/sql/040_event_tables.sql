-- Event tables and the version rule. TEMPLATE: db/sql/apply.sh runs this file
-- once per schema with the psql variable "schema" set to core and to replay
-- (and tests/benchmark/index_benchmark.py to bench). Every object is created
-- in that schema; the dimensions and extractions always come from core.

SET search_path = :"schema", core;

-- Latest known version of each earthquake. One row per USGS id.
CREATE TABLE event_current (
    event_id           text PRIMARY KEY,                      -- USGS id
    source             text NOT NULL CHECK (source IN ('usgs_feed', 'usgs_catalog')),
    event_time         timestamptz NOT NULL,                  -- properties.time
    -- UTC day of the event; follows event_time on every revision.
    event_date         date GENERATED ALWAYS AS ((event_time AT TIME ZONE 'UTC')::date) STORED
                       NOT NULL REFERENCES core.dim_date (date_id),
    updated_at         timestamptz NOT NULL,                  -- properties.updated, version identity
    magnitude          double precision,                      -- NULL kept and shown as ND; no minimum
    mag_type           text,
    longitude          double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude           double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    depth_km           double precision,                      -- may be negative (above sea level)
    place              text,
    country_id         text REFERENCES core.dim_country (country_id),  -- NULL = no country polygon
    quality_flags      text[] NOT NULL DEFAULT '{}',          -- anomalies flagged, not rejected
    first_ingested_at  timestamptz NOT NULL DEFAULT now(),
    ingested_at        timestamptz NOT NULL DEFAULT now(),    -- last write by the consumer
    replayed_at        timestamptz,                           -- schema rule in 050_schema_rules.sql
    -- PostgreSQL sorts NaN above +Infinity, so "< Infinity" excludes both;
    -- the coordinate range checks already exclude them for longitude and latitude.
    CONSTRAINT event_current_magnitude_finite
        CHECK (magnitude > '-Infinity'::double precision AND magnitude < 'Infinity'::double precision),
    CONSTRAINT event_current_depth_finite
        CHECK (depth_km > '-Infinity'::double precision AND depth_km < 'Infinity'::double precision)
);

-- Every distinct version observed. (event_id, updated_at) is the version identity.
CREATE TABLE event_version (
    event_id         text NOT NULL REFERENCES event_current (event_id) ON DELETE CASCADE,
    updated_at       timestamptz NOT NULL,
    source           text NOT NULL CHECK (source IN ('usgs_feed', 'usgs_catalog')),
    event_time       timestamptz NOT NULL,
    magnitude        double precision,
    mag_type         text,
    depth_km         double precision,
    longitude        double precision NOT NULL,
    latitude         double precision NOT NULL,
    payload          jsonb NOT NULL,                          -- original USGS Feature, untransformed
    received_at      timestamptz NOT NULL DEFAULT now(),
    kafka_topic      text NOT NULL,                           -- message that first brought it
    kafka_partition  integer NOT NULL,
    kafka_offset     bigint NOT NULL,
    PRIMARY KEY (event_id, updated_at)
);

-- Latest version of each event confirmed by Kafka to the producer.
CREATE TABLE publish_state (
    event_id      text PRIMARY KEY,
    updated_at    timestamptz NOT NULL,
    published_at  timestamptz NOT NULL DEFAULT now()
);

-- Messages the consumer could not treat as a valid earthquake version.
CREATE TABLE quarantine (
    quarantine_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kafka_topic      text NOT NULL,
    kafka_partition  integer NOT NULL,
    kafka_offset     bigint NOT NULL,
    event_id         text,                                    -- when it could be read
    reason_codes     text[] NOT NULL CHECK (cardinality(reason_codes) > 0),
    reason_detail    text NOT NULL,
    payload          jsonb,                                   -- original message when it is JSON
    raw_text         text,                                    -- original message when it is not
    is_synthetic     boolean NOT NULL DEFAULT false,          -- damaged on purpose for tests
    quarantined_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kafka_topic, kafka_partition, kafka_offset),
    CHECK (payload IS NOT NULL OR raw_text IS NOT NULL)
);

-- Versions of USGS items that are not earthquakes (quarry blast, explosion...).
CREATE TABLE excluded_event (
    event_id       text NOT NULL,
    updated_at     timestamptz NOT NULL,
    event_type     text,                                      -- properties.type as received
    reason_code    text NOT NULL DEFAULT 'not_earthquake',
    extraction_id  bigint REFERENCES core.extraction (extraction_id),
    payload        jsonb NOT NULL,
    first_seen_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, updated_at)
);

-- One row per message processed by the consumer: an ingestion audit,
-- not a source of earthquake counts.
CREATE TABLE message_log (
    kafka_topic      text NOT NULL,
    kafka_partition  integer NOT NULL,
    kafka_offset     bigint NOT NULL,
    event_id         text,
    updated_at       timestamptz,
    outcome          text NOT NULL CHECK (outcome IN ('new', 'revised', 'stale', 'duplicate', 'quarantined')),
    produced_at      timestamptz,                             -- ingested_at of the message (producer)
    processed_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kafka_topic, kafka_partition, kafka_offset)
);

-- The version rule (FAQ 12), shared by core and replay.
--   new        unknown event: current row created, version added
--   revised    later updated_at: current row replaced, version added
--   duplicate  updated_at already seen: nothing changes
--   stale      earlier updated_at never seen: version added, current row untouched
-- Atomic (single statement call inside the caller's transaction), idempotent
-- and monotonic: the current row never moves back to an earlier version.
CREATE FUNCTION apply_event_version(
    p_event_id         text,
    p_source           text,
    p_event_time       timestamptz,
    p_updated_at       timestamptz,
    p_magnitude        double precision,
    p_mag_type         text,
    p_longitude        double precision,
    p_latitude         double precision,
    p_depth_km         double precision,
    p_place            text,
    p_country_id       text,
    p_quality_flags    text[],
    p_payload          jsonb,
    p_kafka_topic      text,
    p_kafka_partition  integer,
    p_kafka_offset     bigint,
    p_replayed_at      timestamptz DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql
SET search_path = :"schema", core
AS $$
DECLARE
    v_inserted       boolean;
    v_version_added  boolean;
BEGIN
    INSERT INTO event_current AS cur (
        event_id, source, event_time, updated_at, magnitude, mag_type,
        longitude, latitude, depth_km, place, country_id, quality_flags, replayed_at
    )
    VALUES (
        p_event_id, p_source, p_event_time, p_updated_at, p_magnitude, p_mag_type,
        p_longitude, p_latitude, p_depth_km, p_place, p_country_id,
        coalesce(p_quality_flags, '{}'), p_replayed_at
    )
    ON CONFLICT (event_id) DO UPDATE
    SET source        = EXCLUDED.source,
        event_time    = EXCLUDED.event_time,
        updated_at    = EXCLUDED.updated_at,
        magnitude     = EXCLUDED.magnitude,
        mag_type      = EXCLUDED.mag_type,
        longitude     = EXCLUDED.longitude,
        latitude      = EXCLUDED.latitude,
        depth_km      = EXCLUDED.depth_km,
        place         = EXCLUDED.place,
        country_id    = EXCLUDED.country_id,
        quality_flags = EXCLUDED.quality_flags,
        replayed_at   = EXCLUDED.replayed_at,
        ingested_at   = now()
        -- first_ingested_at is deliberately left as it was.
    WHERE EXCLUDED.updated_at > cur.updated_at
    RETURNING (xmax = 0) INTO v_inserted;     -- xmax = 0: the row was inserted, not updated

    INSERT INTO event_version (
        event_id, updated_at, source, event_time, magnitude, mag_type, depth_km,
        longitude, latitude, payload, kafka_topic, kafka_partition, kafka_offset
    )
    VALUES (
        p_event_id, p_updated_at, p_source, p_event_time, p_magnitude, p_mag_type, p_depth_km,
        p_longitude, p_latitude, p_payload, p_kafka_topic, p_kafka_partition, p_kafka_offset
    )
    ON CONFLICT (event_id, updated_at) DO NOTHING;
    v_version_added := FOUND;

    IF v_inserted THEN
        RETURN 'new';
    ELSIF v_inserted IS NOT NULL THEN
        RETURN 'revised';
    ELSIF v_version_added THEN
        RETURN 'stale';
    ELSE
        RETURN 'duplicate';
    END IF;
END;
$$;

COMMENT ON FUNCTION apply_event_version IS
    'Applies one USGS version: returns new, revised, stale or duplicate (contracts/database.md)';

RESET search_path;
