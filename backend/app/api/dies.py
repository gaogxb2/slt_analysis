from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DieRecord, Lot, ChipLog
from app.schemas import DieRecordOut

router = APIRouter(prefix="/api/dies", tags=["dies"])


@router.get("/search", response_model=list[DieRecordOut])
def search_dies(
    die_id: str | None = Query(None),
    barcode: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(DieRecord, Lot).join(Lot, DieRecord.lot_id == Lot.id)
    if die_id:
        q = q.filter(DieRecord.die_id.contains(die_id.upper()))
    if barcode:
        q = q.filter(DieRecord.barcode.contains(barcode))
    if not die_id and not barcode:
        return []

    rows = q.order_by(Lot.lot_no, DieRecord.round_key, DieRecord.id).limit(500).all()
    out = []
    for d, lot in rows:
        log_status = None
        chip_log_id = None
        cl = db.query(ChipLog).filter(ChipLog.die_record_id == d.id).first()
        if cl:
            chip_log_id = cl.id
            log_status = "linked"
        else:
            log_status = "missing"
        out.append(
            DieRecordOut(
                id=d.id,
                die_id=d.die_id,
                barcode=d.barcode,
                lot_no=lot.lot_no,
                stage=lot.stage,
                round_key=d.round_key or "",
                test_mode=d.test_mode,
                site=d.site,
                error_code=d.error_code,
                software_bin=d.software_bin,
                boot_on=d.boot_on,
                tj=d.tj,
                bios_time=d.bios_time,
                test_time=d.test_time,
                temperature=d.temperature,
                log_status=log_status,
                chip_log_id=chip_log_id,
            )
        )
    return out
