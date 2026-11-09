#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh" "${1:-demo}"
if [[ ! -f "$RUNTIME_ENV" ]]; then
  printf '请先运行 ./scripts/start.sh %s\n' "$MODE" >&2
  exit 1
fi
"${COMPOSE[@]}" exec -T api python -m app.cli evaluate
"${COMPOSE[@]}" exec -T api python -m app.cli warehouse

if [[ "$MODE" = "demo" ]]; then
  "${COMPOSE[@]}" exec -T api python /srv/verify_http.py --base-url http://127.0.0.1:8000
fi
