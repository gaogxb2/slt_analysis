from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
LOGS_DIR = PROJECT_ROOT / "logs"
# 兼容旧引用
TESTDATA_DIR = LOGS_DIR
TESTLOG_DIR = LOGS_DIR

DATABASE_URL = f"sqlite:///{DATA_DIR / 'slt.db'}"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
