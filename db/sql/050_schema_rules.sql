-- Rules that differ between the real and the replay schema. The event tables
-- themselves are identical (040_event_tables.sql); only these rules tell them apart.

-- Real data is never a replay.
ALTER TABLE core.event_current
    ADD CONSTRAINT event_current_not_replayed CHECK (replayed_at IS NULL);

-- Every replayed event records when it was replayed; event_time stays the
-- original occurrence time.
ALTER TABLE replay.event_current
    ALTER COLUMN replayed_at SET NOT NULL;

-- Empties every event table of the replay schema so a replay can start from
-- zero. SECURITY DEFINER: the writer may call it without holding TRUNCATE,
-- and the fixed search_path means it can only ever touch replay. There is no
-- equivalent in core on purpose.
CREATE FUNCTION replay.reset() RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    TRUNCATE replay.event_version, replay.event_current, replay.quarantine,
             replay.excluded_event, replay.publish_state, replay.message_log;
$$;

COMMENT ON FUNCTION replay.reset() IS 'Empties the replay event tables; core is never touched';
