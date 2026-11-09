#!/usr/bin/env bash
# Shared by scripts; does not create state when sourced.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-demo}"
case "$MODE" in
  demo|live) ;;
  *) printf '用法: %s demo|live\n' "${0##*/}" >&2; exit 2 ;;
esac
# The selected mode and its persisted password must win over a caller's shell.
export DATA_MODE="$MODE"
unset DB_PASSWORD
if ! command -v docker >/dev/null 2>&1; then
  printf '未找到 Docker，请安装并启动 Docker Desktop 或 Docker Engine + Compose。\n' >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  printf '需要 Docker Compose v2（docker compose）。\n' >&2
  exit 1
fi
RUNTIME_ENV="$PROJECT_ROOT/.runtime/$MODE.env"
COMPOSE=(docker compose --project-name "vibescope-$MODE" --file "$PROJECT_ROOT/compose.yaml")
if [[ -f "$PROJECT_ROOT/.env" ]]; then COMPOSE+=(--env-file "$PROJECT_ROOT/.env"); fi
COMPOSE+=(--env-file "$RUNTIME_ENV")
