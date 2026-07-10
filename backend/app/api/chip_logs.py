from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChipLog, ChipLogDieId, DieRecord, Lot, OneTest
from app.schemas import (
    ChipLogDetailOut,
    ChipLogDieIdOut,
    OneTestOut,
    SumCompareOut,
)
from app.services.log_utils import normalize_die_id

router = APIRouter(tags=["chip-logs"])


def _chip_log_detail(db: Session, cl: ChipLog, lot: Lot) -> ChipLogDetailOut:
    onetests = db.query(OneTest).filter(OneTest.chip_log_id == cl.id).all()
    die_ids = (
        db.query(ChipLogDieId)
        .filter(ChipLogDieId.chip_log_id == cl.id)
        .order_by(ChipLogDieId.ordinal)
        .all()
    )
    sum_compare = None
    if cl.die_record_id:
        die = db.query(DieRecord).filter(DieRecord.id == cl.die_record_id).first()
        if die:
            sum_compare = SumCompareOut(
                boot_on=die.boot_on or "",
                booton=die.booton,
                tested=die.tested,
                software_bin=die.software_bin or 0,
                site=die.site or 0,
                test_mode=die.test_mode or "",
                test_time=die.test_time or "",
            )

    return ChipLogDetailOut(
        id=cl.id,
        lot_no=lot.lot_no,
        stage=lot.stage,
        test_mode=cl.test_mode or "",
        round_key=cl.round_key or "",
        site=cl.site or 0,
        primary_die_id=cl.primary_die_id or "",
        barcode=cl.barcode or "",
        pf=cl.pf or "",
        soft_bin=cl.soft_bin or 0,
        test_time=cl.test_time or "",
        test_start=cl.test_start or "",
        file_path=cl.file_path or "",
        die_record_id=cl.die_record_id,
        onetests=[
            OneTestOut(
                test_txt=o.test_txt or "",
                pattern=o.pattern or "",
                result=o.result or "",
                pf=o.pf or "",
                test_time_ms=o.test_time_ms or 0,
            )
            for o in onetests
        ],
        die_ids=[
            ChipLogDieIdOut(
                die_id_str=d.die_id_str or "",
                die_id_name=d.die_id_name or "",
                lot=d.lot or "",
                wafer=d.wafer or "",
                x=d.x or "",
                y=d.y or "",
                ordinal=d.ordinal or 1,
            )
            for d in die_ids
        ],
        sum_compare=sum_compare,
        header={
            "CUSTOMER_LOT_ID": lot.lot_no,
            "TEST_SITE": str(cl.site or ""),
            "TEST_STAGE": lot.stage,
            "TEST_FLOW": cl.test_mode or "",
            "TEST_START": cl.test_start or "",
        },
    )


@router.get("/api/chip-logs/{chip_log_id}", response_model=ChipLogDetailOut)
def get_chip_log(chip_log_id: int, db: Session = Depends(get_db)):
    cl = db.query(ChipLog).filter(ChipLog.id == chip_log_id).first()
    if not cl:
        raise HTTPException(404, "Chip log not found")
    lot = db.query(Lot).filter(Lot.id == cl.lot_id).first()
    if not lot:
        raise HTTPException(404, "Lot not found")
    return _chip_log_detail(db, cl, lot)


@router.get("/api/dies/{die_record_id}/log", response_model=ChipLogDetailOut)
def get_die_log(die_record_id: int, db: Session = Depends(get_db)):
    die = db.query(DieRecord).filter(DieRecord.id == die_record_id).first()
    if not die:
        raise HTTPException(404, "Die record not found")
    cl = (
        db.query(ChipLog)
        .filter(ChipLog.die_record_id == die_record_id)
        .first()
    )
    if not cl:
        candidates = (
            db.query(ChipLog)
            .filter(
                ChipLog.lot_id == die.lot_id,
                ChipLog.round_key == die.round_key,
                ChipLog.site == die.site,
            )
            .all()
        )
        norm = normalize_die_id(die.die_id)
        cl = next((c for c in candidates if normalize_die_id(c.primary_die_id) == norm), None)
    if not cl:
        raise HTTPException(404, "No log found for this die")
    lot = db.query(Lot).filter(Lot.id == die.lot_id).first()
    return _chip_log_detail(db, cl, lot)
