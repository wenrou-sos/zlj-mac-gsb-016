#!/usr/bin/env bash
# 一键测试：后端 pytest（含服务启动冒烟）+ 前端构建校验
set -euo pipefail
cd "$(dirname "$0")"

echo "=========== 1/3 后端单元与接口测试 ==========="
cd backend
python3 -m pytest tests/ -v
cd ..

echo ""
echo "=========== 2/3 后端真实启动冒烟测试 ==========="
SMOKE_DB="$(pwd)/.local-data/smoke_$$.db"
mkdir -p .local-data
trap 'kill $SMOKE_PID 2>/dev/null || true; rm -f "$SMOKE_DB"' EXIT
DATABASE_URL="sqlite:///$SMOKE_DB" SEED_DEMO=1 \
  python3 -m uvicorn --app-dir backend app.main:app --host 127.0.0.1 --port 8765 &
SMOKE_PID=$!

ok=0
for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8765/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
[ "$ok" = "1" ] || { echo "❌ 后端启动失败"; exit 1; }

curl -sf http://127.0.0.1:8765/health | grep -q '"ok"'
echo "  ✅ /health 正常"
curl -sf http://127.0.0.1:8765/api/batches | grep -q 'LOT-A'
echo "  ✅ 演示批次数据已写入"
curl -sf http://127.0.0.1:8765/api/batches/compare >/dev/null
echo "  ✅ /api/batches/compare 正常"
curl -sf http://127.0.0.1:8765/openapi.json >/dev/null
echo "  ✅ OpenAPI 文档正常"
kill $SMOKE_PID 2>/dev/null || true
trap 'rm -f "$SMOKE_DB"' EXIT

echo ""
echo "=========== 3/3 前端构建测试 ==========="
cd frontend
[ -d node_modules ] || npm install --no-audit --no-fund
npm run build
cd ..

echo ""
echo "🎉 全部测试通过"
