from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BinSummary, ChipLog, DieRecord, ImportLog, Lot, SiteCounter, SumFile, TestRound
from app.schemas import (
    LotDetailOut,
    LotSummaryOut,
    ReconcileOut,
    ReconcileRowOut,
    ReconcileSummaryOut,
    RoundDieOut,
    TestRoundOut,
    ValidationIssueOut,
    FieldDiffOut,
)
from app.services.log_utils import normalize_die_id
from app.services.sum_log_reconciler import reconcile_lot
from app.services.importer import compute_fail_breakdowns, compute_final_yield, merge_and_persist_lot
from app.services.round_merger import merge_parsed_sums
from app.services.sum_parser import parse_sum_file
from app.services.types import parse_round_order
from app.services.validator import validate_lot_rounds

router = APIRouter(prefix="/api/lots", tags=["lots"])


def _round_to_out(db: Session, tr: TestRound, lot_id: int) -> TestRoundOut:
    bins = db.query(BinSummary).filter(BinSummary.round_id == tr.id).all()
    sites = db.query(SiteCounter).filter(SiteCounter.round_id == tr.id).all()
    log_count = (
        db.query(ChipLog)
        .filter(ChipLog.lot_id == lot_id, ChipLog.round_key == tr.round_key)
        .count()
    )
    matched_count = (
        db.query(ChipLog)
        .filter(
            ChipLog.lot_id == lot_id,
            ChipLog.round_key == tr.round_key,
            ChipLog.die_record_id.isnot(None),
        )
        .count()
    )
    return TestRoundOut(
        id=tr.id,
        round_key=tr.round_key,
        input_qty=tr.input_qty,
        pass_count=tr.pass_count,
        fail_count=tr.fail_count,
        yield_pct=tr.yield_pct,
        start_time=tr.start_time,
        report_date=tr.report_date,
        sub_file_count=tr.sub_file_count,
        log_count=log_count,
        matched_count=matched_count,
        bin_summaries=[
            {
                "sw_category": b.sw_category,
                "hw_bin": b.hw_bin,
                "code": b.code,
                "description": b.description,
                "count": b.count,
                "percent": b.percent,
            }
            for b in bins
        ],
        site_counters=[
            {
                "site_no": s.site_no,
                "counter": s.counter,
                "pass_count": s.pass_count,
                "fail_count": s.fail_count,
                "yield_pct": s.yield_pct,
            }
            for s in sites
        ],
    )


def _lot_summary(db: Session, lot: Lot) -> LotSummaryOut:
    final = compute_final_yield(db, lot)
    breakdowns = compute_fail_breakdowns(db, lot)
    rounds = db.query(TestRound).filter(TestRound.lot_id == lot.id).all()
    last_report = max((r.report_date for r in rounds if r.report_date), default=None)
    return LotSummaryOut(
        id=lot.id,
        lot_no=lot.lot_no,
        stage=lot.stage,
        bin=lot.bin,
        traveler_qty=lot.traveler_qty,
        lot_start_date=lot.lot_start_date,
        temperature=lot.temperature,
        input_qty=final["input_qty"],
        final_pass=final["final_pass"],
        final_fail=final["final_fail"],
        final_yield_pct=final["yield_pct"],
        last_report_date=last_report,
        round_count=len(rounds),
        final_fail_breakdown=breakdowns["final_fail_breakdown"],
        initial_fail_breakdown=breakdowns["initial_fail_breakdown"],
    )


@router.get("", response_model=list[LotSummaryOut])
def list_lots(
    lot_no: str | None = Query(None),
    stage: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Lot)
    if lot_no:
        q = q.filter(Lot.lot_no.contains(lot_no))
    if stage:
        q = q.filter(Lot.stage == stage)
    lots = q.order_by(Lot.lot_no).all()
    return [_lot_summary(db, lot) for lot in lots]


@router.get("/{lot_no}", response_model=LotDetailOut)
def get_lot(lot_no: str, stage: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(Lot).filter(Lot.lot_no == lot_no)
    if stage:
        q = q.filter(Lot.stage == stage)
    lot = q.first()
    if not lot:
        from fastapi import HTTPException
        raise HTTPException(404, "Lot not found")

    rounds = (
        db.query(TestRound)
        .filter(TestRound.lot_id == lot.id)
        .all()
    )
    rounds = sorted(rounds, key=lambda r: parse_round_order(r.round_key))

    sum_files = db.query(SumFile).filter(SumFile.lot_id == lot.id).all()
    final = compute_final_yield(db, lot)

    # Validation
    from collections import defaultdict
    from app.services.types import ParsedSum

    by_round: dict = defaultdict(list)
    all_parsed: list[ParsedSum] = []
    for sf in sum_files:
        if sf.file_path and Path(sf.file_path).exists():
            p = parse_sum_file(Path(sf.file_path))
            by_round[p.round_key].append(p)
            all_parsed.append(p)
    merged = [merge_parsed_sums(by_round[k]) for k in sorted(by_round.keys(), key=parse_round_order)]
    issues = validate_lot_rounds(merged, all_parsed)

    return LotDetailOut(
        id=lot.id,
        lot_no=lot.lot_no,
        stage=lot.stage,
        bin=lot.bin,
        traveler_qty=lot.traveler_qty,
        lot_start_date=lot.lot_start_date,
        temperature=lot.temperature,
        final_stats=final,
        rounds=[_round_to_out(db, r, lot.id) for r in rounds],
        sum_files=sum_files,
        validation_issues=[ValidationIssueOut(**i.__dict__) for i in issues],
    )


@router.get("/{lot_no}/rounds/{round_key}", response_model=TestRoundOut)
def get_round(
    lot_no: str,
    round_key: str,
    stage: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Lot).filter(Lot.lot_no == lot_no)
    if stage:
        q = q.filter(Lot.stage == stage)
    lot = q.first()
    if not lot:
        from fastapi import HTTPException
        raise HTTPException(404, "Lot not found")

    tr = (
        db.query(TestRound)
        .filter(TestRound.lot_id == lot.id, TestRound.round_key == round_key)
        .first()
    )
    if not tr:
        from fastapi import HTTPException
        raise HTTPException(404, "Round not found")
    return _round_to_out(db, tr, lot.id)


@router.get("/{lot_no}/reconcile", response_model=ReconcileOut)
def get_reconcile(
    lot_no: str,
    stage: str | None = Query(None),
    test_mode: str | None = Query(None),
    round_key: str | None = Query(None),
    only_fail: bool = Query(False),
    only_abnormal: bool = Query(False),
    db: Session = Depends(get_db),
):
    result = reconcile_lot(
        db,
        lot_no,
        stage=stage,
        test_mode=test_mode,
        round_key=round_key,
        only_fail=only_fail,
        only_abnormal=only_abnormal,
    )
    return ReconcileOut(
        lot_no=result.lot_no,
        stage=result.stage,
        summary=ReconcileSummaryOut(**result.summary.__dict__),
        rows=[
            ReconcileRowOut(
                status=r.status,
                die_record_id=r.die_record_id,
                chip_log_id=r.chip_log_id,
                die_id=r.die_id,
                test_mode=r.test_mode,
                round_key=r.round_key,
                site=r.site,
                barcode=r.barcode,
                sum_boot_on=r.sum_boot_on,
                log_pf=r.log_pf,
                sum_bin=r.sum_bin,
                log_bin=r.log_bin,
                diff_summary=r.diff_summary,
                diffs=[FieldDiffOut(**d.__dict__) for d in r.diffs],
            )
            for r in result.rows
        ],
    )


def _die_log_status(db: Session, die: DieRecord) -> tuple[str, Optional[int]]:
    cl = (
        db.query(ChipLog)
        .filter(ChipLog.die_record_id == die.id)
        .first()
    )
    if not cl:
        cl = (
            db.query(ChipLog)
            .filter(
                ChipLog.lot_id == die.lot_id,
                ChipLog.round_key == die.round_key,
                ChipLog.site == die.site,
                ChipLog.primary_die_id == normalize_die_id(die.die_id),
            )
            .first()
        )
    if not cl:
        return "missing", None
    from app.services.sum_log_reconciler import _detect_diffs

    diffs = _detect_diffs(die, cl)
    if diffs:
        return "mismatch", cl.id
    return "linked", cl.id


@router.get("/{lot_no}/rounds/{round_key}/dies", response_model=list[RoundDieOut])
def get_round_dies(
    lot_no: str,
    round_key: str,
    stage: str | None = Query(None),
    only_fail: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(Lot).filter(Lot.lot_no == lot_no)
    if stage:
        q = q.filter(Lot.stage == stage)
    lot = q.first()
    if not lot:
        from fastapi import HTTPException
        raise HTTPException(404, "Lot not found")

    tr = (
        db.query(TestRound)
        .filter(TestRound.lot_id == lot.id, TestRound.round_key == round_key)
        .first()
    )
    if not tr:
        from fastapi import HTTPException
        raise HTTPException(404, "Round not found")

    dies_q = db.query(DieRecord).filter(DieRecord.round_id == tr.id)
    if only_fail:
        dies_q = dies_q.filter(DieRecord.boot_on == "FAIL")
    dies = dies_q.order_by(DieRecord.site, DieRecord.die_id).all()

    result = []
    for d in dies:
        log_status, chip_log_id = _die_log_status(db, d)
        result.append(
            RoundDieOut(
                id=d.id,
                die_id=d.die_id,
                barcode=d.barcode,
                site=d.site or 0,
                boot_on=d.boot_on or "",
                booton=d.booton,
                tested=d.tested,
                error_code=d.error_code or 0,
                software_bin=d.software_bin or 0,
                test_mode=d.test_mode,
                log_status=log_status,
                chip_log_id=chip_log_id,
            )
        )
    return result
