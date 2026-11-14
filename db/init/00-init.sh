#!/usr/bin/env bash
# Executed by the postgres image only when the data volume is empty.
# Creates the whole model in POSTGRES_DB through the shared db/sql/apply.sh.
set -euo pipefail
export PGUSER="${PGUSER:-$POSTGRES_USER}"
/sql/apply.sh "$POSTGRES_DB"
