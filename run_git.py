#!/usr/bin/env python3
"""从 GitHub 下载 slt_analysis 到 D 盘并启动开发环境（Windows）。

用法:
  python run_git.py              下载/解压后启动开发模式
  python run_git.py dev          同上
  python run_git.py --seed       强制重新入库后再启动
  python run_git.py seed         仅递归扫描 logs 入库
  python run_git.py backend      仅启动后端
  python run_git.py prod         构建前端并由后端单端口托管
  python run_git.py --skip-download  跳过下载，使用 D 盘已有目录

环境变量:
  BACKEND_PORT=8000   FRONTEND_PORT=5173
  DOWNLOAD_TIMEOUT=600  Chrome 下载等待秒数

依赖:
  pip install selenium
  本机已安装 Google Chrome（Selenium 4 会自动匹配 ChromeDriver）
"""
from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
import shutil
import zipfile
from pathlib import Path

GITHUB_ZIP_URL = "https://github.com/gaogxb2/slt_analysis/archive/refs/heads/main.zip"
INSTALL_ROOT = Path("D:/")
ZIP_PATH = INSTALL_ROOT / "slt_analysis-main.zip"
PROJECT_DIR = INSTALL_ROOT / "slt_analysis-main"
DOWNLOAD_TIMEOUT = int(os.environ.get("DOWNLOAD_TIMEOUT", "600"))

ROOT = PROJECT_DIR
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DB_FILE = BACKEND_DIR / "data" / "slt.db"
PYTHON = sys.executable

PROCESSES: list[subprocess.Popen] = []


def _configure_paths(root: Path) -> None:
    global ROOT, BACKEND_DIR, FRONTEND_DIR, DB_FILE
    ROOT = root.resolve()
    BACKEND_DIR = ROOT / "backend"
    FRONTEND_DIR = ROOT / "frontend"
    DB_FILE = BACKEND_DIR / "data" / "slt.db"


def _cleanup_old_downloads() -> None:
    """下载前清理旧 zip/临时文件，避免误判为下载成功。"""
    INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    for pattern in ("slt_analysis*.zip", "*.crdownload"):
        for path in INSTALL_ROOT.glob(pattern):
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    if removed:
        print(f"    已删除旧文件: {', '.join(removed)}")


def _wait_for_zip_download(directory: Path, timeout: int, started_at: float) -> Path:
    print(f"    等待 Chrome 下载完成（最多 {timeout}s）...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(directory.glob("*.crdownload")):
            time.sleep(2)
            continue
        candidates = sorted(
            [p for p in directory.glob("*.zip") if p.name.startswith("slt_analysis")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            st = path.stat()
            if st.st_size > 1024 and st.st_mtime >= started_at - 1:
                return path
        time.sleep(2)
    raise SystemExit(
        f"Chrome 下载超时（{timeout}s）。"
        "请确认已安装 Chrome、D 盘可写，或加大 DOWNLOAD_TIMEOUT。"
    )


def download_repo() -> None:
    _cleanup_old_downloads()
    print(f"==> [下载] 使用 Chrome WebDriver: {GITHUB_ZIP_URL}")
    print(f"    保存目录: {INSTALL_ROOT}")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as e:
        raise SystemExit("请先安装 selenium: pip install selenium") from e

    started_at = time.time()
    download_dir = str(INSTALL_ROOT.resolve())

    options = Options()
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(GITHUB_ZIP_URL)
        downloaded = _wait_for_zip_download(INSTALL_ROOT, DOWNLOAD_TIMEOUT)
        if downloaded.resolve() != ZIP_PATH.resolve():
            if ZIP_PATH.exists():
                ZIP_PATH.unlink()
            shutil.move(str(downloaded), str(ZIP_PATH))
        size = ZIP_PATH.stat().st_size
        print(f"==> [下载] 完成 ({size:,} 字节) -> {ZIP_PATH}")
    except Exception as e:
        raise SystemExit(f"Chrome 下载失败: {e}") from e
    finally:
        driver.quit()


def extract_repo() -> Path:
    if not ZIP_PATH.exists():
        raise SystemExit(f"未找到 zip 文件: {ZIP_PATH}")
    print(f"==> [解压] {ZIP_PATH} -> {INSTALL_ROOT}")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(INSTALL_ROOT)
    if not PROJECT_DIR.is_dir():
        raise SystemExit(f"解压后未找到项目目录: {PROJECT_DIR}")
    print(f"==> [解压] 完成: {PROJECT_DIR}")
    return PROJECT_DIR


def prepare_project(*, skip_download: bool = False) -> Path:
    if skip_download:
        if not PROJECT_DIR.is_dir():
            raise SystemExit(f"--skip-download 指定但目录不存在: {PROJECT_DIR}")
        print(f"==> [跳过下载] 使用已有目录: {PROJECT_DIR}")
        return PROJECT_DIR

    download_repo()
    return extract_repo()


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
    print("==> [SQLite] 初始化数据库并递归扫描 logs 入库...")
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
        description="从 GitHub 下载 slt_analysis 到 D 盘并启动",
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
        help="开发模式下强制重新递归扫描 logs 入库",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="跳过 GitHub 下载与解压，直接使用 D:/slt_analysis-main",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    project_root = prepare_project(skip_download=args.skip_download)
    _configure_paths(project_root)
    os.chdir(project_root)
    print(f"==> [项目] {ROOT}")

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
