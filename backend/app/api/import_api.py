import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import LOGS_DIR, UPLOAD_DIR
from app.database import get_db
from app.models import ImportLog, Lot
from app.schemas import ClearDatabaseOut, ImportLogOut, ImportResultOut
from app.services.db_clear import clear_all_data
from app.services.importer import import_file, merge_and_persist_lot, scan_directory
from app.services.log_importer import import_log_file, scan_log_directory

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/upload", response_model=ImportResultOut)
async def upload_files(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    result = ImportResultOut()
    lot_ids: set = set()

    for uf in files:
        dest = UPLOAD_DIR / uf.filename
        with dest.open("wb") as f:
            shutil.copyfileobj(uf.file, f)
        if dest.suffix.lower() == ".log":
            lot, _, status = import_log_file(db, dest)
            if status == "ok" and lot:
                result.ok.append(uf.filename)
                from app.services.log_importer import link_chip_logs_to_dies
                link_chip_logs_to_dies(db, lot.id)
            else:
                result.errors.append({"file": uf.filename, "error": status})
            continue
        lot, _, status = import_file(db, dest)
        if status == "ok" and lot:
            result.ok.append(uf.filename)
            lot_ids.add(lot.id)
        else:
            result.errors.append({"file": uf.filename, "error": status})

    for lot_id in lot_ids:
        merge_and_persist_lot(db, lot_id)

    return result


@router.post("/scan", response_model=ImportResultOut)
def scan_testdata(
    path: str | None = None,
    db: Session = Depends(get_db),
):
    directory = Path(path) if path else LOGS_DIR
    raw = scan_directory(db, directory)
    return ImportResultOut(ok=raw["ok"], errors=raw["errors"])


@router.post("/scan-logs", response_model=ImportResultOut)
def scan_testlogs(
    path: str | None = None,
    db: Session = Depends(get_db),
):
    directory = Path(path) if path else LOGS_DIR
    raw = scan_log_directory(db, directory)
    return ImportResultOut(ok=raw["ok"], errors=raw["errors"])


@router.get("/status", response_model=list[ImportLogOut])
def import_status(limit: int = 50, db: Session = Depends(get_db)):
    logs = (
        db.query(ImportLog)
        .order_by(ImportLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs


@router.post("/clear-all", response_model=ClearDatabaseOut)
def clear_database(
    confirm: bool = False,
    db: Session = Depends(get_db),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="须传 confirm=true 以确认清空全部数据")
    deleted = clear_all_data(db)
    return ClearDatabaseOut(
        deleted=deleted,
        message=f"已清空数据库，共删除 {deleted['total']} 条记录",
    )
