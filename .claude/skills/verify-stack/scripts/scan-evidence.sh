#!/usr/bin/env bash
# Checks that no secret value from .env appears in the given files or
# directories. Prints only variable names, never values.
#
#   bash .claude/skills/verify-stack/scripts/scan-evidence.sh docs/evidence/002
#
# Exit code: 0 clean, 1 a secret was found, 2 usage error.
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: scan-evidence.sh <file-or-directory>..." >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"
if [ ! -f .env ]; then
  echo "no .env found: nothing to compare against"
  exit 0
fi

found=0
while IFS= read -r line; do
  name="${line%%=*}"
  value="${line#*=}"
  value="${value%$'\r'}"
  value="${value#\"}"; value="${value%\"}"
  value="${value#\'}"; value="${value%\'}"
  # Empty values and the example placeholder are not secrets.
  if [ -z "$value" ] || [ "$value" = "CHANGE_ME_LOCALLY" ]; then
    continue
  fi
  if grep -rqF -- "$value" "$@" 2>/dev/null; then
    echo "LEAK: value of $name found in: $(grep -rlF -- "$value" "$@" | tr '\n' ' ')"
    found=1
  fi
done < <(grep -E '^[A-Z0-9_]*(PASSWORD|TOKEN|SECRET|AUTHTOKEN|DSN|KEY)[A-Z0-9_]*=' .env || true)

if [ "$found" -eq 0 ]; then
  echo "clean: no .env secret found in $*"
fi
exit "$found"
