#!/usr/bin/env bash
# 一键启动：SQLite 建库入库 + 后端 FastAPI + 前端 Vue
#
# 用法:
#   ./run-dev.sh           开发模式（库不存在时自动 seed）
#   ./run-dev.sh --seed    强制重新递归扫描 logs 入库后再启动
#   ./run-dev.sh --backend 仅启动后端
#   ./run-dev.sh --seed-only  仅执行 SQLite 入库，不启动服务
#
# 环境变量:
#   BACKEND_PORT=8000   FRONTEND_PORT=5173
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
DB_FILE="$ROOT/backend/data/slt.db"

FORCE_SEED=0
MODE="dev"

for arg in "$@"; do
  case "$arg" in
    --seed) FORCE_SEED=1 ;;
    --seed-only) MODE="seed-only" ;;
    --backend) MODE="backend" ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
  esac
done

if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "错误: 未找到 python3 或 python" >&2
  exit 1
fi

# ---------- 1. SQLite：建表 + 扫描 SUM/Log 入库 ----------
run_sql_seed() {
  echo "==> [SQLite] 初始化数据库并递归扫描 logs 入库..."
  echo "    数据库文件: $DB_FILE"
  cd "$ROOT/backend"
  $PYTHON seed.py
  echo "==> [SQLite] 入库完成"
}

if [[ "$MODE" == "seed-only" ]]; then
  run_sql_seed
  exit 0
fi

if [[ "$FORCE_SEED" -eq 1 ]] || [[ ! -f "$DB_FILE" ]]; then
  run_sql_seed
else
  echo "==> [SQLite] 使用已有数据库 $DB_FILE（加 --seed 可强制重新入库）"
fi

# ---------- 2. 后端 FastAPI ----------
start_backend() {
  echo "==> [后端] 启动 uvicorn http://127.0.0.1:${BACKEND_PORT}"
  echo "    API 文档: http://127.0.0.1:${BACKEND_PORT}/docs"
  cd "$ROOT/backend"
  exec $PYTHON -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT"
}

if [[ "$MODE" == "backend" ]]; then
  lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
  start_backend
fi

# ---------- 3. 前端 Vue + 后端（并行） ----------
echo "==> [前端] 启动 Vite http://127.0.0.1:${FRONTEND_PORT}"
echo "    开发地址: http://localhost:${FRONTEND_PORT}"

lsof -ti:"$BACKEND_PORT","$FRONTEND_PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

trap 'kill 0' EXIT INT TERM

cd "$ROOT/backend"
$PYTHON -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" &

cd "$ROOT/frontend"
exec npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
