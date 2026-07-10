from sqlalchemy.orm import Session

from app.models import (
    BinSummary,
    ChipLog,
    ChipLogDieId,
    DieRecord,
    ImportLog,
    Lot,
    OneTest,
    SiteCounter,
    SumFile,
    TestRound,
)


def clear_all_data(db: Session) -> dict[str, int]:
    """删除数据库中全部业务数据（保留表结构）。"""
    counts: dict[str, int] = {}
    counts["onetests"] = db.query(OneTest).delete(synchronize_session=False)
    counts["chip_log_die_ids"] = db.query(ChipLogDieId).delete(synchronize_session=False)
    db.query(ChipLog).update({ChipLog.die_record_id: None}, synchronize_session=False)
    counts["chip_logs"] = db.query(ChipLog).delete(synchronize_session=False)
    counts["die_records"] = db.query(DieRecord).delete(synchronize_session=False)
    counts["bin_summaries"] = db.query(BinSummary).delete(synchronize_session=False)
    counts["site_counters"] = db.query(SiteCounter).delete(synchronize_session=False)
    counts["test_rounds"] = db.query(TestRound).delete(synchronize_session=False)
    counts["sum_files"] = db.query(SumFile).delete(synchronize_session=False)
    counts["lots"] = db.query(Lot).delete(synchronize_session=False)
    counts["import_logs"] = db.query(ImportLog).delete(synchronize_session=False)
    db.commit()
    counts["total"] = sum(counts.values())
    return counts
