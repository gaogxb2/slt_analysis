from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ValidationIssueOut(BaseModel):
    level: str
    code: str
    message: str
    round_key: Optional[str] = None


class BinSummaryOut(BaseModel):
    sw_category: int
    hw_bin: int
    code: int
    description: str
    count: int
    percent: float


class SiteCounterOut(BaseModel):
    site_no: int
    counter: int
    pass_count: int
    fail_count: int
    yield_pct: float


class SumFileOut(BaseModel):
    id: int
    filename: str
    test_mode: str
    round_key: str
    sub_batch: int
    input_qty: int
    pass_count: int
    fail_count: int
    yield_pct: float
    start_time: Optional[str] = None
    report_date: Optional[str] = None

    class Config:
        from_attributes = True


class TestRoundOut(BaseModel):
    id: int
    round_key: str
    input_qty: int
    pass_count: int
    fail_count: int
    yield_pct: float
    start_time: Optional[str] = None
    report_date: Optional[str] = None
    sub_file_count: int
    log_count: int = 0
    matched_count: int = 0
    bin_summaries: List[BinSummaryOut] = []
    site_counters: List[SiteCounterOut] = []

    class Config:
        from_attributes = True


class FailBreakdownOut(BaseModel):
    code: int
    description: str
    count: int
    sw_category: Optional[int] = None
    hw_bin: Optional[int] = None


class LotSummaryOut(BaseModel):
    id: int
    lot_no: str
    stage: str
    bin: int
    traveler_qty: int
    lot_start_date: Optional[str] = None
    temperature: Optional[int] = None
    input_qty: int = 0
    final_pass: int = 0
    final_fail: int = 0
    final_yield_pct: float = 0.0
    last_report_date: Optional[str] = None
    round_count: int = 0
    final_fail_breakdown: List[FailBreakdownOut] = []
    initial_fail_breakdown: List[FailBreakdownOut] = []

    class Config:
        from_attributes = True


class LotDetailOut(BaseModel):
    id: int
    lot_no: str
    stage: str
    bin: int
    traveler_qty: int
    lot_start_date: Optional[str] = None
    temperature: Optional[int] = None
    final_stats: dict
    rounds: List[TestRoundOut] = []
    sum_files: List[SumFileOut] = []
    validation_issues: List[ValidationIssueOut] = []

    class Config:
        from_attributes = True


class DieRecordOut(BaseModel):
    id: Optional[int] = None
    die_id: str
    barcode: Optional[str] = None
    lot_no: str
    stage: str
    round_key: str
    test_mode: Optional[str] = None
    site: int
    error_code: int
    software_bin: int
    boot_on: str
    booton: Optional[str] = None
    tested: Optional[str] = None
    tj: Optional[str] = None
    bios_time: Optional[str] = None
    test_time: Optional[str] = None
    temperature: Optional[int] = None
    log_status: Optional[str] = None
    chip_log_id: Optional[int] = None

    class Config:
        from_attributes = True


class OneTestOut(BaseModel):
    test_txt: str
    pattern: str
    result: str
    pf: str
    test_time_ms: int


class ChipLogDieIdOut(BaseModel):
    die_id_str: str
    die_id_name: str
    lot: str
    wafer: str
    x: str
    y: str
    ordinal: int


class SumCompareOut(BaseModel):
    boot_on: str
    booton: Optional[str] = None
    tested: Optional[str] = None
    software_bin: int
    site: int
    test_mode: str
    test_time: str


class ChipLogDetailOut(BaseModel):
    id: int
    lot_no: str
    stage: str
    test_mode: str
    round_key: str
    site: int
    primary_die_id: str
    barcode: str
    pf: str
    soft_bin: int
    test_time: str
    test_start: str
    file_path: str
    die_record_id: Optional[int] = None
    onetests: List[OneTestOut] = []
    die_ids: List[ChipLogDieIdOut] = []
    sum_compare: Optional[SumCompareOut] = None
    header: dict = {}


class ReconcileSummaryOut(BaseModel):
    sum_count: int
    log_count: int
    matched_count: int
    sum_only_count: int
    log_only_count: int
    mismatch_count: int


class FieldDiffOut(BaseModel):
    field: str
    sum_value: str
    log_value: str


class ReconcileRowOut(BaseModel):
    status: str
    die_record_id: Optional[int] = None
    chip_log_id: Optional[int] = None
    die_id: str
    test_mode: str
    round_key: str
    site: int
    barcode: str
    sum_boot_on: str = ""
    log_pf: str = ""
    sum_bin: int = 0
    log_bin: int = 0
    diff_summary: str = ""
    diffs: List[FieldDiffOut] = []


class ReconcileOut(BaseModel):
    lot_no: str
    stage: str
    summary: ReconcileSummaryOut
    rows: List[ReconcileRowOut] = []


class RoundDieOut(BaseModel):
    id: int
    die_id: str
    barcode: Optional[str] = None
    site: int
    boot_on: str
    booton: Optional[str] = None
    tested: Optional[str] = None
    error_code: int
    software_bin: int
    test_mode: Optional[str] = None
    log_status: str
    chip_log_id: Optional[int] = None


class OverviewOut(BaseModel):
    lot_count: int
    total_input: int
    total_final_pass: int
    avg_yield_pct: float
    final_fail_breakdown: List[FailBreakdownOut] = []
    lots: List[LotSummaryOut] = []


class ImportLogOut(BaseModel):
    id: int
    action: str
    filename: Optional[str] = None
    status: str
    message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ImportResultOut(BaseModel):
    ok: List[str] = []
    errors: List[dict] = []


class ClearDatabaseOut(BaseModel):
    deleted: dict[str, int]
    message: str


class MaterialRoundFailBinOut(BaseModel):
    code: int
    description: str
    count: int


class MaterialRoundOut(BaseModel):
    round_key: str
    input_qty: int
    pass_count: int
    fail_count: int
    yield_pct: float
    fail_bins: List[MaterialRoundFailBinOut] = []


class MaterialRoundRowOut(BaseModel):
    lot_no: str
    stage: str
    round_key: str
    label: str
    input_qty: int
    pass_count: int
    fail_count: int
    yield_pct: float
    fail_bins: List[MaterialRoundFailBinOut] = []


class MaterialMemberOut(BaseModel):
    lot_no: str
    stage: str
    input_qty: int
    final_pass: int
    final_fail: int
    final_yield_pct: float
    round_count: int
    rounds: List[MaterialRoundOut] = []
    final_fail_breakdown: List[FailBreakdownOut] = []


class MaterialGroupSummaryOut(BaseModel):
    material_key: str
    material_label: str
    member_count: int
    lot_nos: List[str] = []
    stages: List[str] = []


class MaterialGroupOut(BaseModel):
    material_key: str
    material_label: str
    member_count: int
    members: List[MaterialMemberOut] = []
    round_rows: List[MaterialRoundRowOut] = []
