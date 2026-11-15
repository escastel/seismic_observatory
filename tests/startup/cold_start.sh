#!/usr/bin/env bash
# Ten cold starts of the five services, timed (SC-002, quickstart V1).
#
#   bash tests/startup/cold_start.sh [runs] [output]
#
# DESTRUCTIVE: every run executes `docker compose down -v`, which deletes the
# local database and the Kafka volume. Ask before running it.
#
# Builds the images once, then repeats: down -v, up -d, and waits until the
# five services are healthy. The time of each start excludes the build.
# Writes a Markdown table (default docs/evidence/002/cold-starts.md).
set -euo pipefail

runs="${1:-10}"
output="${2:-docs/evidence/002/cold-starts.md}"
limit_seconds=180
services=(postgres kafka producer consumer api)

cd "$(git rev-parse --show-toplevel)"

healthy_count() {
    local count=0 service status
    for service in "${services[@]}"; do
        status="$(docker compose ps --format '{{.Status}}' "$service" 2>/dev/null || true)"
        [[ "$status" == *"(healthy)"* ]] && count=$((count + 1))
    done
    echo "$count"
}

now_ms() { date +%s%3N; }

echo "building images once"
docker compose build --quiet

times=()
for run in $(seq 1 "$runs"); do
    docker compose down -v --remove-orphans >/dev/null 2>&1
    start="$(now_ms)"
    docker compose up -d >/dev/null 2>&1
    while [[ "$(healthy_count)" -lt ${#services[@]} ]]; do
        if (( ($(now_ms) - start) / 1000 > 600 )); then
            echo "run $run: services not healthy after 600 s" >&2
            docker compose ps -a >&2
            exit 1
        fi
        sleep 1
    done
    elapsed_ms=$(( $(now_ms) - start ))
    times+=("$elapsed_ms")
    printf 'run %2d: %6.1f s\n' "$run" "$(awk -v ms="$elapsed_ms" 'BEGIN { print ms / 1000 }')"
done

sorted=($(printf '%s\n' "${times[@]}" | sort -n))
count=${#sorted[@]}
if (( count % 2 == 1 )); then
    median_ms=${sorted[$((count / 2))]}
else
    median_ms=$(( (sorted[count / 2 - 1] + sorted[count / 2]) / 2 ))
fi
seconds() { awk -v ms="$1" 'BEGIN { printf "%.1f", ms / 1000 }' | tr . ,; }
over_limit=0
for ms in "${times[@]}"; do
    (( ms > limit_seconds * 1000 )) && over_limit=$((over_limit + 1))
done

{
    echo "# Arranques desde cero (V1 repetido, SC-002)"
    echo
    bash .claude/skills/verify-stack/scripts/evidence-header.sh
    echo "- Orden: \`bash tests/startup/cold_start.sh $runs\`"
    echo
    echo "Imágenes construidas una vez antes de medir. Cada arranque: \`docker compose down -v\`,"
    echo "\`docker compose up -d\` y espera, consultando \`docker compose ps\` cada segundo, hasta que"
    echo "los cinco servicios (${services[*]}) están \`healthy\`."
    echo
    echo "| Arranque | Tiempo hasta cinco servicios sanos (s) |"
    echo "|---:|---:|"
    for i in "${!times[@]}"; do
        echo "| $((i + 1)) | $(seconds "${times[$i]}") |"
    done
    echo
    echo "| Mínimo | Mediana | Máximo | Por encima de ${limit_seconds} s |"
    echo "|---:|---:|---:|---:|"
    echo "| $(seconds "${sorted[0]}") | $(seconds "$median_ms") | $(seconds "${sorted[$((count - 1))]}") | $over_limit de $count |"
    echo
    if (( over_limit == 0 )); then
        echo "Resultado: SUPERADA. Los $count arranques quedan por debajo de ${limit_seconds} s."
    else
        echo "Resultado: FALLIDA. $over_limit de $count arranques superan ${limit_seconds} s."
    fi
} > "$output"
echo "written $output"
