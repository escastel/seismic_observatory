-- Changes for spec 004 (consumer quality). TEMPLATE: apply.sh runs this file once per
-- schema (core and replay). Idempotent, so it can also be applied to an existing database:
--   apply.sh <database> 041_consumer_quality.sql
-- Justification: specs/004-consumer-quality/research.md R9.

SET search_path = :"schema", core;

-- Reprocessing of the quarantine (FR-016, FR-017): which rows were reprocessed, when and how.
ALTER TABLE quarantine
    ADD COLUMN IF NOT EXISTS reprocessed_at          timestamptz,
    ADD COLUMN IF NOT EXISTS reprocess_result        text,
    ADD COLUMN IF NOT EXISTS reprocess_reason_codes  text[];

ALTER TABLE quarantine DROP CONSTRAINT IF EXISTS quarantine_reprocess_result_check;
ALTER TABLE quarantine ADD CONSTRAINT quarantine_reprocess_result_check
    CHECK (reprocess_result IN ('recovered_new', 'recovered_revised', 'recovered_stale',
                                'recovered_duplicate', 'still_rejected'));

ALTER TABLE quarantine DROP CONSTRAINT IF EXISTS quarantine_reprocess_pair_check;
ALTER TABLE quarantine ADD CONSTRAINT quarantine_reprocess_pair_check
    CHECK ((reprocessed_at IS NULL) = (reprocess_result IS NULL));

-- A reprocessed message gets a second row with the same position: attempt 0 is the original
-- treatment, attempt 1 the reprocessing (clarification 2 of the spec).
ALTER TABLE message_log ADD COLUMN IF NOT EXISTS attempt smallint NOT NULL DEFAULT 0;

DO $$
DECLARE
    has_attempt boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
        WHERE i.indrelid = 'message_log'::regclass AND i.indisprimary AND a.attname = 'attempt'
    ) INTO has_attempt;
    IF NOT has_attempt THEN
        ALTER TABLE message_log DROP CONSTRAINT message_log_pkey;
        ALTER TABLE message_log ADD PRIMARY KEY (kafka_topic, kafka_partition, kafka_offset, attempt);
    END IF;
END
$$;

-- A message about an item that is not an earthquake is recorded as excluded (FR-009, FR-015).
ALTER TABLE message_log DROP CONSTRAINT IF EXISTS message_log_outcome_check;
ALTER TABLE message_log ADD CONSTRAINT message_log_outcome_check
    CHECK (outcome IN ('new', 'revised', 'stale', 'duplicate', 'excluded', 'quarantined'));

RESET search_path;
