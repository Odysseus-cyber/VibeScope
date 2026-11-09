#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh" "${1:-demo}"
if [[ ! -f "$RUNTIME_ENV" ]]; then
  printf '%s 模式尚未初始化，无需停止。\n' "$MODE"
  exit 0
fi
"${COMPOSE[@]}" down
printf '已停止 %s 模式，数据库与运行数据保留。\n' "$MODE"
