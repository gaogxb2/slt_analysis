from collections import defaultdict
from dataclasses import dataclass, field
from typing import List

from app.services.types import (
    BinRow,
    DieRow,
    ParsedSum,
    SiteCounterRow,
    SiteSummaryBlock,
)


@dataclass
class MergedRound:
    round_key: str
    meta_base: dict
    input_qty: int = 0
    pass_count: int = 0
    fail_count: int = 0
    yield_pct: float = 0.0
    start_time: str = ""
    report_date: str = ""
    sub_file_count: int = 0
    source_files: List[str] = field(default_factory=list)
    test_modes: List[str] = field(default_factory=list)
    site_summaries: List[SiteSummaryBlock] = field(default_factory=list)
    total_bins: List[BinRow] = field(default_factory=list)
    site_counters: List[SiteCounterRow] = field(default_factory=list)
    dies: List[DieRow] = field(default_factory=list)


def merge_parsed_sums(parsed_list: List[ParsedSum]) -> MergedRound:
    if not parsed_list:
        raise ValueError("No parsed sums to merge")

    round_key = parsed_list[0].round_key
    meta_base = dict(parsed_list[0].meta)

    input_qty = 0
    pass_count = 0
    fail_count = 0
    start_times: List[str] = []
    report_dates: List[str] = []
    source_files: List[str] = []
    test_modes: List[str] = []
    all_dies: List[DieRow] = []

    bin_agg: dict = defaultdict(int)
    bin_meta: dict = {}
    site_agg: dict = defaultdict(lambda: {"counter": 0, "pass": 0, "fail": 0})

    for p in parsed_list:
        input_qty += p.meta.get("input_qty", 0)
        pass_count += p.meta.get("pass_count", 0)
        fail_count += p.meta.get("fail_count", 0)
        if p.meta.get("start_time"):
            start_times.append(p.meta["start_time"])
        if p.meta.get("report_date"):
            report_dates.append(p.meta["report_date"])
        if p.source_file:
            source_files.append(p.source_file)
        test_modes.append(p.test_mode)
        all_dies.extend(p.dies)

        for b in p.total_bins:
            key = (b.sw_category, b.hw_bin, b.code, b.description)
            bin_agg[key] += b.count
            bin_meta[key] = b

        for sc in p.site_counters:
            s = site_agg[sc.site_no]
            s["counter"] += sc.counter
            s["pass"] += sc.pass_count
            s["fail"] += sc.fail_count

    yield_pct = (pass_count / input_qty * 100) if input_qty else 0.0
    total_bin = sum(bin_agg.values())
    total_bins = []
    for key, cnt in sorted(bin_agg.items(), key=lambda x: -x[1]):
        b = bin_meta[key]
        pct = (cnt / total_bin * 100) if total_bin else 0
        total_bins.append(BinRow(b.sw_category, b.hw_bin, cnt, pct, b.code, b.description))

    site_counters = []
    for site_no in sorted(site_agg.keys()):
        s = site_agg[site_no]
        yld = (s["pass"] / s["counter"] * 100) if s["counter"] else 0
        site_counters.append(
            SiteCounterRow(site_no, s["counter"], s["pass"], s["fail"], yld)
        )

    # Rebuild per-site summaries from dies
    site_summaries = _site_summaries_from_dies(all_dies)

    return MergedRound(
        round_key=round_key,
        meta_base=meta_base,
        input_qty=input_qty,
        pass_count=pass_count,
        fail_count=fail_count,
        yield_pct=yield_pct,
        start_time=min(start_times) if start_times else "",
        report_date=max(report_dates) if report_dates else "",
        sub_file_count=len(parsed_list),
        source_files=source_files,
        test_modes=test_modes,
        site_summaries=site_summaries,
        total_bins=total_bins,
        site_counters=site_counters,
        dies=all_dies,
    )


FAIL_BIN_MAP = {
    4000: (1111, 2, "E2"),
    4001: (1212, 3, "E3"),
    4002: (1313, 4, "E1"),
}


def _die_to_bin(d: DieRow) -> BinRow:
    if d.error_code == 1000:
        return BinRow(1000, 1, 1, 0, 1000, "PASS")
    sw, hw, desc = FAIL_BIN_MAP.get(d.error_code, (d.software_bin, 0, str(d.error_code)))
    return BinRow(sw, hw, 1, 0, d.error_code, desc)


def _site_summaries_from_dies(dies: List[DieRow]) -> List[SiteSummaryBlock]:
    site_bins: dict = defaultdict(list)
    for d in dies:
        site_bins[d.site].append(_die_to_bin(d))

    result = []
    for site_no in sorted(site_bins.keys()):
        agg: dict = defaultdict(int)
        meta: dict = {}
        for b in site_bins[site_no]:
            key = (b.sw_category, b.hw_bin, b.code, b.description)
            agg[key] += 1
            meta[key] = b
        total = sum(agg.values())
        bins = []
        for key, cnt in sorted(agg.items(), key=lambda x: -x[1]):
            b = meta[key]
            pct = (cnt / total * 100) if total else 0
            bins.append(BinRow(b.sw_category, b.hw_bin, cnt, pct, b.code, b.description))
        result.append(SiteSummaryBlock(site_no=site_no, bins=bins))
    return result
