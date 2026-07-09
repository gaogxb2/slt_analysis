import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def parse_test_mode(test_mode: str) -> tuple[str, int]:
    """Extract round_key and sub_batch from Test Mode like M2R2+1 -> (M2R2, 1)."""
    m = re.match(r"^(.+)\+(\d+)$", test_mode.strip())
    if m:
        return m.group(1), int(m.group(2))
    return test_mode.strip(), 1


def parse_round_order(round_key: str) -> tuple[int, int]:
    """Sort key: M2=0, M2R1=1, M2R2=2, ..."""
    m = re.search(r"R(\d+)$", round_key)
    if m:
        return (1, int(m.group(1)))
    return (0, 0)


@dataclass
class BinRow:
    sw_category: int
    hw_bin: int
    count: int
    percent: float
    code: int
    description: str


@dataclass
class SiteSummaryBlock:
    site_no: int
    bins: List[BinRow] = field(default_factory=list)


@dataclass
class SiteCounterRow:
    site_no: int
    counter: int
    pass_count: int
    fail_count: int
    yield_pct: float


@dataclass
class DieRow:
    error_code: int
    software_bin: int
    die_id: str
    tj: str
    temperature: int
    site: int
    bios_time: str
    test_time: str
    barcode: str
    boot_on: str


@dataclass
class ParsedSum:
    meta: Dict[str, Any]
    test_mode: str
    round_key: str
    sub_batch: int
    site_summaries: List[SiteSummaryBlock] = field(default_factory=list)
    total_bins: List[BinRow] = field(default_factory=list)
    site_counters: List[SiteCounterRow] = field(default_factory=list)
    dies: List[DieRow] = field(default_factory=list)
    source_file: Optional[str] = None


@dataclass
class OneTestRow:
    test_txt: str
    pattern: str
    result: str
    pf: str
    test_time_ms: int


@dataclass
class DieIdGroup:
    die_id_str: str
    die_id_name: str
    die_id_lot: str
    die_id_wafer: str
    die_id_x: str
    die_id_y: str


@dataclass
class ParsedLog:
    lot_no: str
    site: int
    stage: str
    test_flow: str
    round_key: str
    sub_batch: int
    test_start: str
    onetests: List[OneTestRow] = field(default_factory=list)
    soft_bin: int = 0
    chip_pf: str = ""
    chip_test_time: str = ""
    chip_test_start: str = ""
    die_id_groups: List[DieIdGroup] = field(default_factory=list)
    barcode: Optional[str] = None
    source_file: Optional[str] = None
