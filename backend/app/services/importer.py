from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import (
    BinSummary,
    DieRecord,
    ImportLog,
    Lot,
    SiteCounter,
    SumFile,
    TestRound,
)
from app.services.round_merger import MergedRound, merge_parsed_sums
from app.services.sum_parser import parse_sum_file
from app.services.types import ParsedSum, parse_round_order
from app.services.validator import validate_lot_rounds


def import_file(db: Session, path: Path) -> tuple[Optional[Lot], Optional[ParsedSum], str]:
    path = Path(path)
    if not path.exists():
        return None, None, f"File not found: {path}"

    try:
        parsed = parse_sum_file(path)
    except Exception as e:
        log = ImportLog(action="import", filename=path.name, status="error", message=str(e))
        db.add(log)
        db.commit()
        return None, None, str(e)

    lot_no = parsed.meta.get("lot_no", "")
    stage = parsed.meta.get("stage", "")
    if not lot_no:
        msg = "Missing LOT NO."
        db.add(ImportLog(action="import", filename=path.name, status="error", message=msg))
        db.commit()
        return None, None, msg

    lot = db.query(Lot).filter(Lot.lot_no == lot_no, Lot.stage == stage).first()
    if not lot:
        lot = Lot(
            lot_no=lot_no,
            stage=stage,
            bin=parsed.meta.get("bin", 1),
            traveler_qty=parsed.meta.get("traveler_qty", 0),
            lot_start_date=parsed.meta.get("lot_start_date"),
            temperature=parsed.meta.get("temperature"),
        )
        db.add(lot)
        db.flush()
    else:
        lot.bin = parsed.meta.get("bin", lot.bin)
        lot.traveler_qty = parsed.meta.get("traveler_qty", lot.traveler_qty)
        lot.temperature = parsed.meta.get("temperature", lot.temperature)

    existing = (
        db.query(SumFile)
        .filter(SumFile.lot_id == lot.id, SumFile.test_mode == parsed.test_mode)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    sf = SumFile(
        lot_id=lot.id,
        filename=path.name,
        test_mode=parsed.test_mode,
        round_key=parsed.round_key,
        sub_batch=parsed.sub_batch,
        input_qty=parsed.meta.get("input_qty", 0),
        pass_count=parsed.meta.get("pass_count", 0),
        fail_count=parsed.meta.get("fail_count", 0),
        yield_pct=parsed.meta.get("yield_pct", 0),
        start_time=parsed.meta.get("start_time"),
        report_date=parsed.meta.get("report_date"),
        file_path=str(path),
    )
    db.add(sf)

    db.add(
        ImportLog(
            action="import",
            filename=path.name,
            status="ok",
            message=f"LOT {lot_no} mode {parsed.test_mode}",
        )
    )
    db.commit()
    db.refresh(lot)
    return lot, parsed, "ok"


def merge_and_persist_lot(db: Session, lot_id: int) -> List[MergedRound]:
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        return []

    sum_files = db.query(SumFile).filter(SumFile.lot_id == lot_id).all()
    by_round: dict = defaultdict(list)
    all_parsed: List[ParsedSum] = []

    for sf in sum_files:
        if sf.file_path and Path(sf.file_path).exists():
            parsed = parse_sum_file(Path(sf.file_path))
            by_round[parsed.round_key].append(parsed)
            all_parsed.append(parsed)

    # Clear existing merged data
    old_rounds = db.query(TestRound).filter(TestRound.lot_id == lot_id).all()
    for tr in old_rounds:
        db.delete(tr)
    db.query(DieRecord).filter(DieRecord.lot_id == lot_id).delete()
    db.flush()

    merged_rounds: List[MergedRound] = []
    for round_key in sorted(by_round.keys(), key=parse_round_order):
        merged = merge_parsed_sums(by_round[round_key])
        merged_rounds.append(merged)
        _persist_round(db, lot, merged, by_round[round_key])

    db.commit()
    return merged_rounds


def _persist_round(db: Session, lot: Lot, merged: MergedRound, source_parsed: List[ParsedSum]):
    tr = TestRound(
        lot_id=lot.id,
        round_key=merged.round_key,
        input_qty=merged.input_qty,
        pass_count=merged.pass_count,
        fail_count=merged.fail_count,
        yield_pct=merged.yield_pct,
        start_time=merged.start_time,
        report_date=merged.report_date,
        sub_file_count=merged.sub_file_count,
        is_merged=1,
    )
    db.add(tr)
    db.flush()

    for b in merged.total_bins:
        db.add(
            BinSummary(
                round_id=tr.id,
                sw_category=b.sw_category,
                hw_bin=b.hw_bin,
                code=b.code,
                description=b.description,
                count=b.count,
                percent=b.percent,
            )
        )

    for sc in merged.site_counters:
        db.add(
            SiteCounter(
                round_id=tr.id,
                site_no=sc.site_no,
                counter=sc.counter,
                pass_count=sc.pass_count,
                fail_count=sc.fail_count,
                yield_pct=sc.yield_pct,
            )
        )

    die_mode_map: dict[tuple, str] = {}
    for p in source_parsed:
        for d in p.dies:
            die_mode_map[(d.site, d.die_id, d.barcode)] = p.test_mode

    for d in merged.dies:
        test_mode = die_mode_map.get((d.site, d.die_id, d.barcode), "")
        db.add(
            DieRecord(
                round_id=tr.id,
                lot_id=lot.id,
                die_id=d.die_id,
                barcode=d.barcode,
                site=d.site,
                error_code=d.error_code,
                software_bin=d.software_bin,
                boot_on=d.boot_on,
                tj=d.tj,
                bios_time=d.bios_time,
                test_time=d.test_time,
                temperature=d.temperature,
                round_key=merged.round_key,
                test_mode=test_mode,
            )
        )


def scan_directory(db: Session, directory: Path) -> dict:
    directory = Path(directory)
    results = {"ok": [], "errors": []}
    seen_modes: set = set()

    for path in sorted(directory.rglob("*.SUM")):
        rel = str(path.relative_to(directory))
        lot, parsed, status = import_file(db, path)
        if status != "ok" or not lot or not parsed:
            results["errors"].append({"file": rel, "error": status})
            continue
        key = (lot.id, parsed.test_mode)
        if key in seen_modes:
            results["errors"].append({"file": rel, "error": "duplicate test_mode skipped merge"})
        seen_modes.add(key)
        results["ok"].append(rel)

    lot_ids = {row[0] for row in db.query(Lot.id).all()}
    for lot_id in lot_ids:
        merge_and_persist_lot(db, lot_id)

    return results


def compute_final_yield(db: Session, lot: Lot) -> dict:
    rounds = (
        db.query(TestRound)
        .filter(TestRound.lot_id == lot.id)
        .order_by(TestRound.round_key)
        .all()
    )
    if not rounds:
        return {"input_qty": 0, "final_pass": 0, "final_fail": 0, "yield_pct": 0.0}

    first_round = min(rounds, key=lambda r: parse_round_order(r.round_key))
    input_qty = first_round.input_qty

    passed_dies = set()
    all_dies = db.query(DieRecord).filter(DieRecord.lot_id == lot.id).all()
    for d in all_dies:
        if d.boot_on and d.boot_on.upper() == "PASS":
            passed_dies.add(d.die_id)

    # Initial round die ids
    first_ids = {
        d.die_id
        for d in all_dies
        if d.round_key == first_round.round_key
    }
    if not first_ids:
        first_ids = {d.die_id for d in all_dies}

    final_pass = len([did for did in first_ids if did in passed_dies])
    denom = len(first_ids) if first_ids else input_qty
    final_fail = denom - final_pass
    yield_pct = (final_pass / denom * 100) if denom else 0

    return {
        "input_qty": denom,
        "final_pass": final_pass,
        "final_fail": final_fail,
        "yield_pct": round(yield_pct, 2),
    }


ERROR_DESC_MAP = {
    4000: "E2",
    4001: "E3",
    4002: "E1",
}


def _fail_label_from_die(d: DieRecord) -> tuple[int, str]:
    code = d.error_code or 0
    desc = ERROR_DESC_MAP.get(code, str(code))
    return code, desc


def compute_fail_breakdowns(db: Session, lot: Lot) -> dict:
    """初测 Fail 分布 + 最终仍未 Pass 的 Fail 类型分布。"""
    rounds = (
        db.query(TestRound)
        .filter(TestRound.lot_id == lot.id)
        .all()
    )
    if not rounds:
        return {"final_fail_breakdown": [], "initial_fail_breakdown": []}

    first_round = min(rounds, key=lambda r: parse_round_order(r.round_key))
    all_dies = db.query(DieRecord).filter(DieRecord.lot_id == lot.id).all()

    passed_dies = {
        d.die_id for d in all_dies if d.boot_on and d.boot_on.upper() == "PASS"
    }
    first_ids = {d.die_id for d in all_dies if d.round_key == first_round.round_key}
    if not first_ids:
        first_ids = {d.die_id for d in all_dies}

    still_fail_ids = first_ids - passed_dies

    last_die: dict[str, DieRecord] = {}
    for d in all_dies:
        if d.die_id not in still_fail_ids:
            continue
        order = parse_round_order(d.round_key or "")
        prev = last_die.get(d.die_id)
        if prev is None or order > parse_round_order(prev.round_key or ""):
            last_die[d.die_id] = d

    final_agg: dict[tuple[int, str], int] = {}
    for d in last_die.values():
        key = _fail_label_from_die(d)
        final_agg[key] = final_agg.get(key, 0) + 1

    final_fail_breakdown = [
        {"code": code, "description": desc, "count": cnt}
        for (code, desc), cnt in sorted(final_agg.items(), key=lambda x: -x[1])
    ]

    initial_agg: dict[tuple[int, str], int] = {}
    for d in all_dies:
        if d.round_key != first_round.round_key:
            continue
        if d.boot_on and d.boot_on.upper() == "PASS":
            continue
        key = _fail_label_from_die(d)
        initial_agg[key] = initial_agg.get(key, 0) + 1

    initial_fail_breakdown = [
        {"code": code, "description": desc, "count": cnt}
        for (code, desc), cnt in sorted(initial_agg.items(), key=lambda x: -x[1])
    ]

    return {
        "final_fail_breakdown": final_fail_breakdown,
        "initial_fail_breakdown": initial_fail_breakdown,
    }


def aggregate_fail_breakdowns(
    breakdowns: list[list],
) -> list[dict]:
    agg: dict[tuple[int, str], int] = {}
    for items in breakdowns:
        for item in items:
            if hasattr(item, "code"):
                code, desc, cnt = item.code, item.description, item.count
            else:
                code, desc, cnt = item["code"], item["description"], item["count"]
            key = (code, desc)
            agg[key] = agg.get(key, 0) + cnt
    return [
        {"code": code, "description": desc, "count": cnt}
        for (code, desc), cnt in sorted(agg.items(), key=lambda x: -x[1])
    ]
