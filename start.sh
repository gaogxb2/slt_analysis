#!/usr/bin/env bash
# 启动 SLT 测试统计 Web 应用
#
# 用法:
#   ./start.sh dev      开发模式：后端 8000 + 前端 5173（默认）
#   ./start.sh backend  仅启动后端
#   ./start.sh prod     生产模式：构建前端并由后端单端口 8000 托管
#   ./start.sh seed     递归扫描 logs 入库（不启动服务）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-dev}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "错误: 未找到 python3 或 python" >&2
  exit 1
fi

cd "$ROOT/backend"

run_seed() {
  echo "==> 递归扫描 logs 入库..."
  $PYTHON seed.py
}

start_backend() {
  echo "==> 启动后端 http://127.0.0.1:${BACKEND_PORT}"
  echo "    API 文档: http://127.0.0.1:${BACKEND_PORT}/docs"
  exec $PYTHON -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT"
}

start_backend_prod() {
  echo "==> 启动后端（生产） http://127.0.0.1:${BACKEND_PORT}"
  exec $PYTHON -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
}

case "$MODE" in
  seed)
    run_seed
    exit 0
    ;;
  backend)
    start_backend
    ;;
  prod)
    echo "==> 构建前端..."
    cd "$ROOT/frontend"
    npm run build
    cd "$ROOT/backend"
    start_backend_prod
    ;;
  dev)
    # 若数据库不存在则自动 seed
    if [[ ! -f "$ROOT/backend/data/slt.db" ]]; then
      run_seed
    fi
    echo "==> 开发模式：后端 ${BACKEND_PORT} + 前端 ${FRONTEND_PORT}"
    echo "    前端: http://localhost:${FRONTEND_PORT}"
    echo "    后端: http://127.0.0.1:${BACKEND_PORT}"
    trap 'kill 0' EXIT INT TERM
    $PYTHON -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" &
    cd "$ROOT/frontend"
    exec npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
    ;;
  *)
    echo "用法: $0 [dev|backend|prod|seed]" >&2
    exit 1
    ;;
esac
