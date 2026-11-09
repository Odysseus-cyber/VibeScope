#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh" "${1:-demo}"
if ! docker info >/dev/null 2>&1; then
  printf 'Docker 尚未启动，请启动后重试。\n' >&2
  exit 1
fi
if [[ ! -f "$RUNTIME_ENV" ]]; then
  umask 077
  mkdir -p "$PROJECT_ROOT/.runtime"
  LOCAL_DB_PASSWORD="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
  printf 'DATA_MODE=%s\nDB_PASSWORD=%s\n' "$MODE" "$LOCAL_DB_PASSWORD" > "$RUNTIME_ENV"
  unset LOCAL_DB_PASSWORD
fi
printf '启动 VibeScope %s 模式；首次运行会构建镜像并初始化数据库。\n' "$MODE"
"${COMPOSE[@]}" up --build --detach --wait --wait-timeout 240
LOCAL_WEB_BIND="$("${COMPOSE[@]}" port frontend 80)"
printf '\n服务已启动：http://%s\n' "$LOCAL_WEB_BIND"
printf '查看日志: ./scripts/logs.sh %s\n停止保留数据: ./scripts/stop.sh %s\n' "$MODE" "$MODE"
