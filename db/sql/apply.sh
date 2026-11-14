#!/usr/bin/env bash
# Apply the whole data model to one database.
#
#   apply.sh <database>
#
# Connection: standard libpq variables (PGHOST, PGPORT, PGUSER, PGPASSWORD).
# Inside the postgres container during initialisation they are unset and psql
# uses the local socket; the test container sets them to reach postgres:5432.
#
# Required variables: DB_WRITER_PASSWORD, DB_READER_PASSWORD.
# Optional: CATALOG_PATH, path of the countries GeoJSON *on the database
# server* (default /catalog/paises.geojson).
#
# Files NNN_*.sql run once, in numeric order. Template files run once per
# schema with the psql variable "schema" set to core and then to replay.
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 <database>" >&2
    exit 2
fi
database="$1"
sql_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
catalog_path="${CATALOG_PATH:-/catalog/paises.geojson}"
: "${DB_WRITER_PASSWORD:?DB_WRITER_PASSWORD is required}"
: "${DB_READER_PASSWORD:?DB_READER_PASSWORD is required}"

templates=(040_event_tables.sql 060_indexes.sql)

run() {
    psql --no-psqlrc --quiet --set ON_ERROR_STOP=1 --single-transaction \
        --dbname "$database" \
        --set catalog_path="$catalog_path" \
        --set writer_password="$DB_WRITER_PASSWORD" \
        --set reader_password="$DB_READER_PASSWORD" \
        "$@"
}

is_template() {
    local name="$1" t
    for t in "${templates[@]}"; do
        [[ "$t" == "$name" ]] && return 0
    done
    return 1
}

shopt -s nullglob
files=("$sql_dir"/[0-9][0-9][0-9]_*.sql)
if [[ ${#files[@]} -eq 0 ]]; then
    echo "no SQL files found in $sql_dir" >&2
    exit 1
fi

for file in "${files[@]}"; do
    name="$(basename "$file")"
    if is_template "$name"; then
        for schema in core replay; do
            echo "applying $name to schema $schema"
            run --set schema="$schema" --file "$file"
        done
    else
        echo "applying $name"
        run --file "$file"
    fi
done
echo "data model applied to database $database"
