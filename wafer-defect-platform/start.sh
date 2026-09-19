#!/usr/bin/env bash
# 晶圆缺陷图谱分析平台 · 一键启动脚本
#
# 用法:
#   ./start.sh            Docker 模式（默认）：构建并启动 PostgreSQL + 后端 + 前端
#   ./start.sh --local    本地开发模式：SQLite + uvicorn 热重载 + Vite 开发服务器
#   ./start.sh --test     运行后端测试套件
#   ./start.sh --stop     停止并清理 Docker 服务
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-docker}"

wait_for() {  # wait_for <url> <名称>
  echo -n "等待 $2 就绪"
  for _ in $(seq 1 60); do
    if curl -sf "$1" >/dev/null 2>&1; then echo " ✓"; return 0; fi
    echo -n "."; sleep 2
  done
  echo " ✗ 超时"; return 1
}

case "$MODE" in
  --stop)
    docker compose down
    echo "服务已停止"
    ;;

  --test)
    cd backend
    python3 -m pip install --user -q -r requirements-dev.txt
    python3 -m pytest
    ;;

  --local)
    echo "==> 本地开发模式（数据库使用 SQLite，无需 Docker）"
    cd backend
    python3 -m pip install --user -q -r requirements-dev.txt
    SEED_DEMO=true python3 -m uvicorn app.main:app --reload --port 8000 &
    BACKEND_PID=$!
    trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT
    cd ../frontend
    [ -d node_modules ] || npm install
    wait_for http://localhost:8000/api/health "后端"
    echo "==> 前端开发服务器: http://localhost:5173 （后端 API: http://localhost:8000/docs）"
    npm run dev
    ;;

  *)
    command -v docker >/dev/null || { echo "未检测到 Docker，请安装 Docker 或使用 ./start.sh --local"; exit 1; }
    echo "==> 构建并启动服务（PostgreSQL + FastAPI + Vue/Nginx）..."
    docker compose up --build -d
    wait_for http://localhost:8000/api/health "后端"
    wait_for http://localhost:8080 "前端"
    echo ""
    echo "==============================================="
    echo "  平台已启动："
    echo "    前端界面:  http://localhost:8080"
    echo "    API 文档:  http://localhost:8000/docs"
    echo "  停止服务:    ./start.sh --stop"
    echo "==============================================="
    ;;
esac
