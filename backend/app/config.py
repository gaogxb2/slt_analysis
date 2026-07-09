from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TESTDATA_DIR = PROJECT_ROOT / "testdata"
TESTLOG_DIR = PROJECT_ROOT / "testdata" / "testlogs"

DATABASE_URL = f"sqlite:///{DATA_DIR / 'slt.db'}"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
