-- Schemas and login roles of the observatory.
-- Applied by db/sql/apply.sh with psql variables writer_password and
-- reader_password. Roles are cluster wide, so this file is idempotent:
-- applying the model to a second database (observatory_test) reuses them.

CREATE SCHEMA core;    -- real data: feed, historical catalog, dimensions, provenance
CREATE SCHEMA replay;  -- accelerated replay, same event tables as core

COMMENT ON SCHEMA core IS 'Real USGS data (live feed and historical catalog), shared dimensions and extraction log';
COMMENT ON SCHEMA replay IS 'Accelerated historical replay, structurally isolated from core';

-- Create the roles only when missing, then (re)set their passwords so the
-- database always matches the current .env.
SELECT format('CREATE ROLE %I LOGIN', role_name)
FROM (VALUES ('observatory_writer'), ('observatory_reader')) AS r(role_name)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.role_name)
\gexec

SELECT format('ALTER ROLE observatory_writer LOGIN PASSWORD %L', :'writer_password') \gexec
SELECT format('ALTER ROLE observatory_reader LOGIN PASSWORD %L', :'reader_password') \gexec

-- Nothing may be created in public by application roles.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
