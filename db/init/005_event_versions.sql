ALTER TABLE dim_geografia
    ADD COLUMN IF NOT EXISTS country_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_geografia_country_id
    ON dim_geografia (country_id)
    WHERE country_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS event_versions (
    version_key BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL,
    updated TIMESTAMPTZ NOT NULL,
    source_topic TEXT NOT NULL CHECK (
        source_topic IN ('terremotos_raw', 'terremotos_replay')
    ),
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (external_id, updated)
);

CREATE INDEX IF NOT EXISTS ix_event_versions_external_id
    ON event_versions (external_id, updated DESC);
