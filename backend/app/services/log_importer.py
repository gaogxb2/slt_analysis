from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ChipLog, ChipLogDieId, ImportLog, Lot, OneTest
from app.services.log_utils import normalize_die_id, primary_die_id
from app.services.testlog_parser import parse_testlog_file, validate_chip_pf
from app.services.types import ParsedLog


def _get_or_create_lot(db: Session, parsed: ParsedLog) -> Lot:
    lot = (
        db.query(Lot)
        .filter(Lot.lot_no == parsed.lot_no, Lot.stage == parsed.stage)
        .first()
    )
    if not lot:
        lot = Lot(lot_no=parsed.lot_no, stage=parsed.stage)
        db.add(lot)
        db.flush()
    return lot


def _primary_die_id(parsed: ParsedLog) -> str:
    if parsed.die_id_groups:
        return parsed.die_id_groups[0].die_id_str
    return ""


def _find_existing_chip_log(db: Session, lot_id: int, parsed: ParsedLog) -> Optional[ChipLog]:
    primary = normalize_die_id(_primary_die_id(parsed))
    return (
        db.query(ChipLog)
        .filter(
            ChipLog.lot_id == lot_id,
            ChipLog.test_mode == parsed.test_flow,
            ChipLog.site == parsed.site,
            ChipLog.primary_die_id == primary,
        )
        .first()
    )


def _persist_chip_log(db: Session, lot: Lot, parsed: ParsedLog, existing: Optional[ChipLog]) -> ChipLog:
    primary = normalize_die_id(_primary_die_id(parsed))
    if existing:
        db.query(OneTest).filter(OneTest.chip_log_id == existing.id).delete()
        db.query(ChipLogDieId).filter(ChipLogDieId.chip_log_id == existing.id).delete()
        cl = existing
    else:
        cl = ChipLog(lot_id=lot.id)
        db.add(cl)

    cl.test_mode = parsed.test_flow
    cl.round_key = parsed.round_key
    cl.sub_batch = parsed.sub_batch
    cl.site = parsed.site
    cl.primary_die_id = primary
    cl.barcode = parsed.barcode or ""
    cl.pf = parsed.chip_pf
    cl.soft_bin = parsed.soft_bin
    cl.test_time = parsed.chip_test_time
    cl.test_start = parsed.chip_test_start or parsed.test_start
    cl.file_path = parsed.source_file

    db.flush()

    for ot in parsed.onetests:
        db.add(
            OneTest(
                chip_log_id=cl.id,
                test_txt=ot.test_txt,
                pattern=ot.pattern,
                result=ot.result,
                pf=ot.pf,
                test_time_ms=ot.test_time_ms,
            )
        )

    for i, g in enumerate(parsed.die_id_groups, start=1):
        db.add(
            ChipLogDieId(
                chip_log_id=cl.id,
                die_id_str=g.die_id_str,
                die_id_name=g.die_id_name,
                lot=g.die_id_lot,
                wafer=g.die_id_wafer,
                x=g.die_id_x,
                y=g.die_id_y,
                ordinal=i,
            )
        )

    return cl


def link_chip_logs_to_dies(db: Session, lot_id: int) -> int:
    from app.models import DieRecord

    logs = db.query(ChipLog).filter(ChipLog.lot_id == lot_id).all()
    dies = db.query(DieRecord).filter(DieRecord.lot_id == lot_id).all()
    die_index: dict[tuple, DieRecord] = {}
    for d in dies:
        key = (
            d.round_key or "",
            d.test_mode or "",
            d.site or 0,
            primary_die_id(d.die_id),
        )
        die_index[key] = d
        fallback = (d.round_key or "", "", d.site or 0, primary_die_id(d.die_id))
        if fallback not in die_index:
            die_index[fallback] = d

    linked = 0
    for cl in logs:
        key = (
            cl.round_key or "",
            cl.test_mode or "",
            cl.site or 0,
            normalize_die_id(cl.primary_die_id),
        )
        die = die_index.get(key)
        if not die:
            key_fb = (cl.round_key or "", "", cl.site or 0, normalize_die_id(cl.primary_die_id))
            die = die_index.get(key_fb)
        if die:
            cl.die_record_id = die.id
            linked += 1

    db.commit()
    return linked


def import_log_file(db: Session, path: Path) -> tuple[Optional[Lot], Optional[ParsedLog], str]:
    path = Path(path)
    if not path.exists():
        return None, None, f"File not found: {path}"

    try:
        parsed = parse_testlog_file(path)
    except Exception as e:
        db.add(ImportLog(action="import_log", filename=path.name, status="error", message=str(e)))
        db.commit()
        return None, None, str(e)

    if not parsed.lot_no:
        msg = "Missing CUSTOMER LOT ID"
        db.add(ImportLog(action="import_log", filename=path.name, status="error", message=msg))
        db.commit()
        return None, None, msg

    if parsed.onetests and parsed.chip_pf:
        if not validate_chip_pf(parsed.onetests, parsed.chip_pf):
            msg = "CHIPINFO P_F does not match ONETEST summary"
            db.add(ImportLog(action="import_log", filename=path.name, status="warning", message=msg))

    lot = _get_or_create_lot(db, parsed)
    existing = _find_existing_chip_log(db, lot.id, parsed)
    if existing and existing.file_path == str(path):
        _persist_chip_log(db, lot, parsed, existing)
    elif existing:
        _persist_chip_log(db, lot, parsed, existing)
    else:
        _persist_chip_log(db, lot, parsed, None)

    db.add(
        ImportLog(
            action="import_log",
            filename=path.name,
            status="ok",
            message=f"LOT {parsed.lot_no} {parsed.test_flow}",
        )
    )
    db.commit()
    db.refresh(lot)
    return lot, parsed, "ok"


def scan_log_directory(db: Session, directory: Path) -> dict:
    directory = Path(directory)
    results = {"ok": [], "errors": []}
    lot_ids: set[int] = set()

    for path in sorted(directory.rglob("*.log")):
        lot, _, status = import_log_file(db, path)
        if status == "ok" and lot:
            results["ok"].append(str(path.relative_to(directory)))
            lot_ids.add(lot.id)
        else:
            results["errors"].append({"file": str(path.relative_to(directory)), "error": status})

    for lot_id in lot_ids:
        link_chip_logs_to_dies(db, lot_id)

    return results
