import re
from collections import defaultdict
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Lot
from app.services.importer import compute_fail_breakdowns, compute_final_yield
from app.services.types import parse_round_order

# 末尾 AA1/AB2/AC3/AD4/AE5 等 → 同一物料族前缀
_SUFFIX_RE = re.compile(r"^(A[A-E]\d)$")


def material_key(lot_no: str) -> str:
    lot_no = (lot_no or "").strip()
    if len(lot_no) >= 3 and _SUFFIX_RE.match(lot_no[-3:]):
        return lot_no[:-3]
    return lot_no


def material_label(key: str) -> str:
    if key and len(key) >= 3:
        return f"{key}*"
    return key


def group_lots_by_material(lots: List[Lot]) -> dict[str, List[Lot]]:
    groups: dict[str, List[Lot]] = defaultdict(list)
    for lot in lots:
        groups[material_key(lot.lot_no)].append(lot)
    for key in groups:
        groups[key].sort(key=lambda l: (l.stage or "", l.lot_no))
    return dict(groups)


def build_material_catalog(db: Session, search: Optional[str] = None) -> list[dict]:
    lots = db.query(Lot).order_by(Lot.lot_no, Lot.stage).all()
    grouped = group_lots_by_material(lots)
    needle = (search or "").strip().upper()
    result = []
    for mkey in sorted(grouped.keys()):
        lot_list = grouped[mkey]
        lot_nos = sorted({l.lot_no for l in lot_list})
        stages = sorted({l.stage for l in lot_list if l.stage})
        if needle:
            hay = " ".join([mkey, material_label(mkey), *lot_nos, *stages]).upper()
            if needle not in hay and not any(needle in ln.upper() for ln in lot_nos):
                continue
        result.append({
            "material_key": mkey,
            "material_label": material_label(mkey),
            "member_count": len(lot_list),
            "lot_nos": lot_nos,
            "stages": stages,
        })
    return result


def build_material_groups(
    db: Session,
    lot_no: Optional[str] = None,
    stage: Optional[str] = None,
    material_keys: Optional[list[str]] = None,
) -> list[dict]:
    from app.models import BinSummary, TestRound

    q = db.query(Lot)
    if lot_no:
        q = q.filter(Lot.lot_no.contains(lot_no))
    if stage:
        q = q.filter(Lot.stage == stage)
    lots = q.order_by(Lot.lot_no, Lot.stage).all()
    grouped = group_lots_by_material(lots)
    if material_keys:
        key_set = set(material_keys)
        grouped = {k: v for k, v in grouped.items() if k in key_set}

    result = []
    for mkey in sorted(grouped.keys()):
        members = []
        round_rows = []
        for lot in grouped[mkey]:
            final = compute_final_yield(db, lot)
            breakdowns = compute_fail_breakdowns(db, lot)
            rounds = (
                db.query(TestRound)
                .filter(TestRound.lot_id == lot.id)
                .all()
            )
            rounds = sorted(rounds, key=lambda r: parse_round_order(r.round_key))
            round_details = []
            for tr in rounds:
                bins = db.query(BinSummary).filter(BinSummary.round_id == tr.id).all()
                fail_bins = [
                    {
                        "code": b.code,
                        "description": b.description,
                        "count": b.count,
                    }
                    for b in bins
                    if b.description and b.description.upper() != "PASS"
                ]
                round_details.append({
                    "round_key": tr.round_key,
                    "input_qty": tr.input_qty,
                    "pass_count": tr.pass_count,
                    "fail_count": tr.fail_count,
                    "yield_pct": tr.yield_pct,
                    "fail_bins": fail_bins,
                })
                round_rows.append({
                    "lot_no": lot.lot_no,
                    "stage": lot.stage,
                    "round_key": tr.round_key,
                    "label": f"{lot.lot_no}/{lot.stage} {tr.round_key}",
                    "input_qty": tr.input_qty,
                    "pass_count": tr.pass_count,
                    "fail_count": tr.fail_count,
                    "yield_pct": tr.yield_pct,
                    "fail_bins": fail_bins,
                })
            members.append({
                "lot_no": lot.lot_no,
                "stage": lot.stage,
                "input_qty": final["input_qty"],
                "final_pass": final["final_pass"],
                "final_fail": final["final_fail"],
                "final_yield_pct": final["yield_pct"],
                "round_count": len(rounds),
                "rounds": round_details,
                "final_fail_breakdown": breakdowns["final_fail_breakdown"],
                "final_stats": final,
            })
        result.append({
            "material_key": mkey,
            "material_label": material_label(mkey),
            "member_count": len(members),
            "members": members,
            "round_rows": round_rows,
        })
    return result
