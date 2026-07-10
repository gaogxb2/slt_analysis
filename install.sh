#!/usr/bin/env bash
# 安装 SLT 测试统计项目依赖（Python 后端 + Vue 前端）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> 项目目录: $ROOT"

# Python 后端
echo ""
echo "==> 安装后端依赖 (pip)..."
cd "$ROOT/backend"
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo "错误: 未找到 python3 或 python" >&2
  exit 1
fi

$PYTHON -m pip install -r requirements.txt

# Node 前端
echo ""
echo "==> 安装前端依赖 (npm)..."
cd "$ROOT/frontend"
if ! command -v npm &>/dev/null; then
  echo "错误: 未找到 npm，请先安装 Node.js" >&2
  exit 1
fi
npm install

echo ""
echo "==> 依赖安装完成"
echo "    首次使用可执行: cd backend && $PYTHON seed.py  递归扫描 logs 入库"
echo "    启动服务: ./start.sh dev"
