CREATE TABLE IF NOT EXISTS dim_geografia (
    geografia_key BIGSERIAL PRIMARY KEY,
    country TEXT NOT NULL,
    continent TEXT NOT NULL,
    subregion TEXT NOT NULL,
    source_dataset TEXT NOT NULL,
    geometry_hash TEXT NOT NULL,
    CONSTRAINT uq_dim_geografia_classification
        UNIQUE (country, continent, subregion, source_dataset, geometry_hash)
);

CREATE INDEX IF NOT EXISTS ix_dim_geografia_country
    ON dim_geografia USING btree (country);

CREATE TABLE IF NOT EXISTS dim_tiempo (
    tiempo_key BIGSERIAL PRIMARY KEY,
    event_date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    day INTEGER NOT NULL CHECK (day BETWEEN 1 AND 31),
    week INTEGER NOT NULL CHECK (week BETWEEN 1 AND 53)
);

CREATE TABLE IF NOT EXISTS fact_sismos (
    sismo_key BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    updated TIMESTAMPTZ NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    magnitude NUMERIC NOT NULL,
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    depth_km DOUBLE PRECISION,
    place TEXT NOT NULL DEFAULT '',
    geografia_key BIGINT NOT NULL REFERENCES dim_geografia (geografia_key),
    tiempo_key BIGINT NOT NULL REFERENCES dim_tiempo (tiempo_key),
    source_topic TEXT NOT NULL CHECK (
        source_topic IN ('terremotos_raw', 'terremotos_replay')
    ),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_sismos_event_time
    ON fact_sismos USING btree (event_time);

CREATE INDEX IF NOT EXISTS ix_fact_sismos_geografia_key
    ON fact_sismos USING btree (geografia_key);

CREATE INDEX IF NOT EXISTS ix_fact_sismos_magnitude
    ON fact_sismos USING btree (magnitude);

CREATE INDEX IF NOT EXISTS ix_fact_sismos_external_id
    ON fact_sismos USING btree (external_id);

CREATE TABLE IF NOT EXISTS cuarentena (
    quarantine_key BIGSERIAL PRIMARY KEY,
    external_id TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_topic TEXT NOT NULL CHECK (
        source_topic IN ('terremotos_raw', 'terremotos_replay')
    ),
    quality_dimension TEXT NOT NULL CHECK (
        quality_dimension IN (
            'Completitud',
            'Validez',
            'Exactitud',
            'Consistencia',
            'Oportunidad',
            'Unicidad'
        )
    ),
    reason_code TEXT NOT NULL,
    reason_detail TEXT NOT NULL,
    payload JSONB NOT NULL,
    kafka_partition INTEGER NOT NULL,
    kafka_offset BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_cuarentena_received_at
    ON cuarentena USING btree (received_at DESC);

CREATE INDEX IF NOT EXISTS ix_cuarentena_quality_dimension
    ON cuarentena USING btree (quality_dimension, received_at DESC);

CREATE INDEX IF NOT EXISTS ix_cuarentena_external_id
    ON cuarentena USING btree (external_id);
