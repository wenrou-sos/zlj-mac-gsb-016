#!/usr/bin/env bash
# 晶圆缺陷图谱分析平台 —— 一键启动脚本
#
# 用法:
#   ./start.sh            使用 Docker Compose 启动（PostgreSQL + FastAPI + Nginx/Vue）
#   ./start.sh --local    本地开发模式（SQLite + uvicorn + Vite dev server，无需 Docker）
#   ./start.sh --rebuild  重新构建镜像后启动
set -euo pipefail
cd "$(dirname "$0")"

MODE="docker"
REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --local) MODE="local" ;;
    --rebuild) REBUILD=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数: $arg" && exit 1 ;;
  esac
done

# ---------------------------------------------------------------- Docker 模式
if [ "$MODE" = "docker" ]; then
  if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then
      DC="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
      DC="docker-compose"
    else
      echo "❌ 未找到 docker compose，请先安装 Docker Compose，或使用 ./start.sh --local"
      exit 1
    fi
  else
    echo "❌ 未找到 Docker。可改用本地模式: ./start.sh --local"
    exit 1
  fi

  echo "🐳 使用 Docker Compose 启动（PostgreSQL + FastAPI + Vue/Nginx）..."
  if [ "$REBUILD" = "1" ]; then
    $DC up -d --build
  else
    $DC up -d --build
  fi

  echo -n "⏳ 等待后端就绪 "
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
      echo " ✅"
      break
    fi
    echo -n "."
    sleep 2
    if [ "$i" = "30" ]; then
      echo " ❌ 后端 60 秒内未就绪，请运行: docker compose logs backend"
      exit 1
    fi
  done

  echo ""
  echo "================ 启动完成 ================"
  echo "  前端页面:   http://localhost:8080"
  echo "  API 文档:   http://localhost:8000/docs"
  echo "  健康检查:   http://localhost:8000/health"
  echo "  PostgreSQL: localhost:5432 (wafer/wafer_pwd)"
  echo ""
  echo "  已自动写入 3 个演示批次（LOT-A 正常 / LOT-B 边缘环 / LOT-C 聚集+划伤）"
  echo "  停止服务:   ./stop.sh"
  echo "  查看日志:   docker compose logs -f"
  echo "=========================================="
  exit 0
fi

# ---------------------------------------------------------------- 本地模式
echo "🖥️  本地开发模式（SQLite + uvicorn + Vite）..."

if ! python3 -c "import fastapi" >/dev/null 2>&1; then
  echo "📦 安装后端依赖..."
  python3 -m pip install -r backend/requirements.txt
fi

mkdir -p .local-data
export DATABASE_URL="sqlite:///$(pwd)/.local-data/wafermap.db"
export SEED_DEMO=1
export CLUSTER_EPS=30

echo "📦 启动 FastAPI (http://localhost:8000)..."
( cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 ) &
BACKEND_PID=$!
echo "$BACKEND_PID" > .local-data/backend.pid

echo "📦 启动 Vite 开发服务器 (http://localhost:5173)..."
( cd frontend && [ -d node_modules ] || npm install; npm run dev ) &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > .local-data/frontend.pid

trap 'echo ""; echo "停止本地服务..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM
echo ""
echo "================ 启动完成 ================"
echo "  前端页面: http://localhost:5173"
echo "  API 文档: http://localhost:8000/docs"
echo "  按 Ctrl+C 停止全部服务"
echo "=========================================="
wait
