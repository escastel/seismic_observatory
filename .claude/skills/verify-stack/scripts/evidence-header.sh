#!/usr/bin/env bash
# Prints the Markdown header every evidence file starts with: when it was
# observed, on which commit and on which machine (constitution, principle IX).
# Works in Git Bash on Windows and in bash on Linux.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

observed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
branch="$(git rev-parse --abbrev-ref HEAD)"
commit="$(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  tree="con cambios sin commit"
else
  tree="árbol limpio"
fi

host="$(uname -srm)"
compose_version="$(docker compose version --short 2>/dev/null || echo 'no disponible')"
if engine="$(docker info --format '{{.ServerVersion}}|{{.OperatingSystem}}|{{.NCPU}}|{{.MemTotal}}' 2>/dev/null)"; then
  IFS='|' read -r engine_version engine_os engine_cpus engine_mem <<<"$engine"
  engine_mem_gib="$(awk -v b="$engine_mem" 'BEGIN { printf "%.1f", b / 1073741824 }')"
  engine_line="Docker ${engine_version} (${engine_os}), Compose ${compose_version}; recursos del motor: ${engine_cpus} CPU, ${engine_mem_gib} GiB"
else
  engine_line="Docker no disponible"
fi

printf -- '- Observado (UTC): %s\n' "$observed_at"
printf -- '- Rama y commit: %s @ %s (%s)\n' "$branch" "$commit" "$tree"
printf -- '- Equipo: %s\n' "$host"
printf -- '- Motor: %s\n' "$engine_line"
