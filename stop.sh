#!/usr/bin/env bash
# 停止平台服务：优先停止 Docker Compose；本地模式则结束记录的进程
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .local-data/backend.pid ]; then
  echo "🛑 停止本地开发服务..."
  for f in .local-data/backend.pid .local-data/frontend.pid; do
    if [ -f "$f" ]; then
      pid=$(cat "$f")
      kill "$pid" 2>/dev/null && echo "  已停止进程 $pid" || true
      rm -f "$f"
    fi
  done
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  if docker compose ps 2>/dev/null | grep -q wafermap; then
    echo "🛑 停止 Docker Compose 服务..."
    docker compose down
    echo "✅ 已停止（数据保留在 Docker 卷 pgdata 中，加 -v 可一并清除）"
    exit 0
  fi
fi

echo "ℹ️ 未检测到正在运行的服务"
