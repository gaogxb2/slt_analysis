from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import ChipLog, DieRecord, Lot
from app.services.log_utils import normalize_test_time, pf_match, primary_die_id


@dataclass
class FieldDiff:
    field: str
    sum_value: str
    log_value: str


@dataclass
class ReconcileRow:
    status: str  # matched | sum_only | log_only | mismatch
    die_record_id: Optional[int] = None
    chip_log_id: Optional[int] = None
    die_id: str = ""
    test_mode: str = ""
    round_key: str = ""
    site: int = 0
    barcode: str = ""
    sum_boot_on: str = ""
    log_pf: str = ""
    sum_bin: int = 0
    log_bin: int = 0
    diffs: List[FieldDiff] = field(default_factory=list)
    diff_summary: str = ""


@dataclass
class ReconcileSummary:
    sum_count: int = 0
    log_count: int = 0
    matched_count: int = 0
    sum_only_count: int = 0
    log_only_count: int = 0
    mismatch_count: int = 0


@dataclass
class ReconcileResult:
    lot_no: str
    stage: str
    summary: ReconcileSummary
    rows: List[ReconcileRow]


def _match_key(
    round_key: str,
    test_mode: str,
    site: int,
    die_id: str,
    barcode: str,
) -> tuple:
    return (round_key or "", test_mode or "", site or 0, primary_die_id(die_id), barcode or "")


def _detect_diffs(die: DieRecord, log: ChipLog) -> List[FieldDiff]:
    diffs: List[FieldDiff] = []
    if not pf_match(die.boot_on or "", log.pf or ""):
        diffs.append(FieldDiff("Pass/Fail", die.boot_on or "", log.pf or ""))
    if die.software_bin and log.soft_bin and die.software_bin != log.soft_bin:
        diffs.append(FieldDiff("Bin", str(die.software_bin), str(log.soft_bin)))
    if die.site and log.site and die.site != log.site:
        diffs.append(FieldDiff("Site", str(die.site), str(log.site)))
    if die.test_mode and log.test_mode and die.test_mode != log.test_mode:
        diffs.append(FieldDiff("Flow", die.test_mode, log.test_mode))
    sum_t = normalize_test_time(die.test_time or "")
    log_t = normalize_test_time(log.test_time or "")
    if sum_t and log_t and sum_t != log_t:
        diffs.append(FieldDiff("Time", die.test_time or "", log.test_time or ""))
    return diffs


def reconcile_lot(
    db: Session,
    lot_no: str,
    stage: Optional[str] = None,
    test_mode: Optional[str] = None,
    round_key: Optional[str] = None,
    only_fail: bool = False,
    only_abnormal: bool = False,
) -> ReconcileResult:
    q = db.query(Lot).filter(Lot.lot_no == lot_no)
    if stage:
        q = q.filter(Lot.stage == stage)
    lot = q.first()
    if not lot:
        return ReconcileResult(
            lot_no=lot_no,
            stage=stage or "",
            summary=ReconcileSummary(),
            rows=[],
        )

    die_q = db.query(DieRecord).filter(DieRecord.lot_id == lot.id)
    log_q = db.query(ChipLog).filter(ChipLog.lot_id == lot.id)
    if test_mode:
        die_q = die_q.filter(DieRecord.test_mode == test_mode)
        log_q = log_q.filter(ChipLog.test_mode == test_mode)
    if round_key:
        die_q = die_q.filter(DieRecord.round_key == round_key)
        log_q = log_q.filter(ChipLog.round_key == round_key)

    dies = die_q.all()
    logs = log_q.all()

    die_by_key: dict[tuple, DieRecord] = {}
    for d in dies:
        die_by_key[_match_key(d.round_key or "", d.test_mode or "", d.site or 0, d.die_id, d.barcode or "")] = d

    log_by_key: dict[tuple, ChipLog] = {}
    for lg in logs:
        log_by_key[_match_key(lg.round_key or "", lg.test_mode or "", lg.site or 0, lg.primary_die_id, lg.barcode or "")] = lg

    all_keys = set(die_by_key.keys()) | set(log_by_key.keys())
    rows: List[ReconcileRow] = []
    summary = ReconcileSummary(sum_count=len(dies), log_count=len(logs))

    for key in sorted(all_keys):
        die = die_by_key.get(key)
        log = log_by_key.get(key)
        if die and log:
            diffs = _detect_diffs(die, log)
            status = "mismatch" if diffs else "matched"
            if status == "matched":
                summary.matched_count += 1
            else:
                summary.mismatch_count += 1
            row = ReconcileRow(
                status=status,
                die_record_id=die.id,
                chip_log_id=log.id,
                die_id=die.die_id,
                test_mode=die.test_mode or log.test_mode or "",
                round_key=die.round_key or "",
                site=die.site or 0,
                barcode=die.barcode or "",
                sum_boot_on=die.boot_on or "",
                log_pf=log.pf or "",
                sum_bin=die.software_bin or 0,
                log_bin=log.soft_bin or 0,
                diffs=diffs,
                diff_summary="; ".join(f"{d.field}" for d in diffs),
            )
        elif die:
            summary.sum_only_count += 1
            row = ReconcileRow(
                status="sum_only",
                die_record_id=die.id,
                die_id=die.die_id,
                test_mode=die.test_mode or "",
                round_key=die.round_key or "",
                site=die.site or 0,
                barcode=die.barcode or "",
                sum_boot_on=die.boot_on or "",
                sum_bin=die.software_bin or 0,
            )
        else:
            summary.log_only_count += 1
            log = log_by_key[key]
            row = ReconcileRow(
                status="log_only",
                chip_log_id=log.id,
                die_id=log.primary_die_id,
                test_mode=log.test_mode or "",
                round_key=log.round_key or "",
                site=log.site or 0,
                barcode=log.barcode or "",
                log_pf=log.pf or "",
                log_bin=log.soft_bin or 0,
            )

        if only_fail and row.sum_boot_on.upper() != "FAIL" and row.log_pf.upper() != "F":
            continue
        if only_abnormal and row.status == "matched":
            continue
        rows.append(row)

    return ReconcileResult(
        lot_no=lot.lot_no,
        stage=lot.stage,
        summary=summary,
        rows=rows,
    )
