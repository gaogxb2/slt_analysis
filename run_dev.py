#!/usr/bin/env python3
"""跨平台启动脚本（Windows / macOS / Linux）。

用法:
  python run_dev.py              开发模式（库不存在时自动 seed）
  python run_dev.py dev          同上
  python run_dev.py --seed       强制重新入库后再启动
  python run_dev.py seed         仅扫描 testdata/testlogs 入库
  python run_dev.py backend      仅启动后端
  python run_dev.py prod         构建前端并由后端单端口托管

环境变量:
  BACKEND_PORT=8000   FRONTEND_PORT=5173
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DB_FILE = BACKEND_DIR / "data" / "slt.db"
PYTHON = sys.executable

PROCESSES: list[subprocess.Popen] = []


def _backend_port() -> int:
    return int(os.environ.get("BACKEND_PORT", "8000"))


def _frontend_port() -> int:
    return int(os.environ.get("FRONTEND_PORT", "5173"))


def _kill_port(port: int) -> None:
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
        pattern = re.compile(rf":{port}\s")
        pids: set[str] = set()
        for line in result.stdout.splitlines():
            if "LISTENING" not in line or not pattern.search(line):
                continue
            parts = line.split()
            if parts:
                pids.add(parts[-1])
        for pid in pids:
            if pid.isdigit() and int(pid) > 0:
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
        return

    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    for pid in result.stdout.split():
        if pid.strip().isdigit():
            subprocess.run(["kill", "-9", pid.strip()], check=False)


def _kill_ports(*ports: int) -> None:
    for port in ports:
        _kill_port(port)


def _terminate_all() -> None:
    for proc in PROCESSES:
        if proc.poll() is not None:
            continue
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
    for proc in PROCESSES:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _register_signal_handlers() -> None:
    def _handler(signum, frame):
        _terminate_all()
        sys.exit(128 + signum if signum else 0)

    signal.signal(signal.SIGINT, _handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handler)


def _popen(cmd: list[str], *, cwd: Path) -> subprocess.Popen:
    kwargs: dict = {
        "cwd": str(cwd),
        "env": os.environ.copy(),
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    PROCESSES.append(proc)
    return proc


def run_seed() -> None:
    print("==> [SQLite] 初始化数据库并扫描 testdata 入库...")
    print(f"    数据库文件: {DB_FILE}")
    subprocess.run([PYTHON, "seed.py"], cwd=str(BACKEND_DIR), check=True)
    print("==> [SQLite] 入库完成")


def start_backend(*, reload: bool = True) -> None:
    port = _backend_port()
    print(f"==> [后端] 启动 uvicorn http://127.0.0.1:{port}")
    print(f"    API 文档: http://127.0.0.1:{port}/docs")
    cmd = [
        PYTHON,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    raise SystemExit(subprocess.call(cmd, cwd=str(BACKEND_DIR)))


def start_dev(*, force_seed: bool = False) -> None:
    if force_seed or not DB_FILE.exists():
        run_seed()
    else:
        print(f"==> [SQLite] 使用已有数据库 {DB_FILE}（加 --seed 可强制重新入库）")

    backend_port = _backend_port()
    frontend_port = _frontend_port()
    print(f"==> [前端] 启动 Vite http://127.0.0.1:{frontend_port}")
    print(f"    开发地址: http://localhost:{frontend_port}")

    _kill_ports(backend_port, frontend_port)
    time.sleep(1)
    _register_signal_handlers()

    backend_cmd = [
        PYTHON,
        "-m",
        "uvicorn",
        "app.main:app",
        "--reload",
        "--host",
        "127.0.0.1",
        "--port",
        str(backend_port),
    ]
    _popen(backend_cmd, cwd=BACKEND_DIR)

    frontend_cmd = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        str(frontend_port),
    ]
    npm_shell = sys.platform == "win32"
    frontend = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        shell=npm_shell,
        env=os.environ.copy(),
    )
    PROCESSES.append(frontend)

    try:
        frontend.wait()
    except KeyboardInterrupt:
        pass
    finally:
        _terminate_all()


def start_prod() -> None:
    if not DB_FILE.exists():
        run_seed()
    port = _backend_port()
    print("==> [前端] 构建生产包...")
    subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND_DIR), check=True, shell=sys.platform == "win32")
    print(f"==> [后端] 启动生产模式 http://127.0.0.1:{port}")
    cmd = [
        PYTHON,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    raise SystemExit(subprocess.call(cmd, cwd=str(BACKEND_DIR)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SLT 测试统计 Web 应用跨平台启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="dev",
        choices=("dev", "backend", "prod", "seed"),
        help="运行模式（默认 dev）",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="开发模式下强制重新扫描 testdata 入库",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.mode == "seed":
        run_seed()
        return

    if args.mode == "backend":
        _kill_ports(_backend_port())
        start_backend(reload=True)
        return

    if args.mode == "prod":
        start_prod()
        return

    start_dev(force_seed=args.seed)


if __name__ == "__main__":
    main()
