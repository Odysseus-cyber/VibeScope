#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh" "${1:-demo}"
if [[ ! -f "$RUNTIME_ENV" ]]; then
  printf '请先运行 ./scripts/start.sh %s\n' "$MODE" >&2
  exit 1
fi
"${COMPOSE[@]}" logs --tail 100 --follow api worker init
