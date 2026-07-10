"""Scan logs directory and seed database."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import LOGS_DIR
from app.database import init_db, SessionLocal
from app.services.importer import scan_directory
from app.services.log_importer import scan_log_directory


def main():
    init_db()
    db = SessionLocal()
    try:
        result = scan_directory(db, LOGS_DIR)
        print(f"SUM OK: {len(result['ok'])} files")
        if result["errors"]:
            print(f"SUM Errors: {result['errors']}")
        log_result = scan_log_directory(db, LOGS_DIR)
        print(f"Log OK: {len(log_result['ok'])} files")
        if log_result["errors"]:
            print(f"Log Errors: {log_result['errors']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
