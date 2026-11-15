-- Privileges of the two application roles. The owner (POSTGRES_USER) keeps
-- every privilege and is the only role that runs DDL.
--
--   observatory_writer  producer and consumer: read and write rows, no DDL
--   observatory_reader  API, the only service reachable from the Internet: read only

-- Functions are executable by PUBLIC by default; only the writer may call ours.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA core, replay FROM PUBLIC;

GRANT USAGE ON SCHEMA core, replay TO observatory_writer, observatory_reader;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core, replay TO observatory_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core, replay TO observatory_writer;
GRANT EXECUTE ON FUNCTION core.apply_event_version, replay.apply_event_version TO observatory_writer;
GRANT EXECUTE ON FUNCTION replay.reset(), core.purge_raw_payload(integer) TO observatory_writer;

GRANT SELECT ON ALL TABLES IN SCHEMA core, replay TO observatory_reader;

-- The writer can change rows but never the shared reference dimensions.
REVOKE INSERT, UPDATE, DELETE ON core.dim_country, core.dim_date FROM observatory_writer;

-- Tables created later by the owner (new migrations) get the same privileges.
ALTER DEFAULT PRIVILEGES IN SCHEMA core, replay
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO observatory_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, replay
    GRANT USAGE, SELECT ON SEQUENCES TO observatory_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, replay
    GRANT SELECT ON TABLES TO observatory_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA core, replay
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
