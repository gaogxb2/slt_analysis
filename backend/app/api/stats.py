from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lot
from app.schemas import OverviewOut
from app.services.importer import aggregate_fail_breakdowns
from app.api.lots import _lot_summary

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview", response_model=OverviewOut)
def overview(
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

    summaries = [_lot_summary(db, lot) for lot in lots]
    total_input = sum(s.input_qty for s in summaries)
    total_pass = sum(s.final_pass for s in summaries)
    avg_yield = (
        sum(s.final_yield_pct for s in summaries) / len(summaries) if summaries else 0
    )
    final_fail_breakdown = aggregate_fail_breakdowns(
        [s.final_fail_breakdown for s in summaries]
    )

    return OverviewOut(
        lot_count=len(summaries),
        total_input=total_input,
        total_final_pass=total_pass,
        avg_yield_pct=round(avg_yield, 2),
        final_fail_breakdown=final_fail_breakdown,
        lots=summaries,
    )
