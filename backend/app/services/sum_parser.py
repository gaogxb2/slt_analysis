import re
from pathlib import Path
from typing import List, Optional

from app.services.log_utils import error_code_to_boot_on
from app.services.types import (
    BinRow,
    DieRow,
    ParsedSum,
    SiteCounterRow,
    SiteSummaryBlock,
    parse_test_mode,
)


META_KEYS = {
    "LOT NO.": "lot_no",
    "Mater Traveler QTY": "traveler_qty",
    "Input Testing QTY": "input_qty",
    "START TIME": "start_time",
    "Bin": "bin",
    "Total Pass": "pass_count",
    "Total Fail": "fail_count",
    "Pass Yield": "yield_pct",
    "Lot Start Date": "lot_start_date",
    "Report Date": "report_date",
    "STAGE": "stage",
    "Test Mode": "test_mode",
    "Temperature": "temperature",
}


def _parse_meta_line(line: str) -> Optional[tuple[str, str]]:
    m = re.match(r"^(.+?)\s*:\s*(.+)$", line.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def _parse_int(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s) or "0")


def _parse_float_pct(s: str) -> float:
    return float(re.sub(r"[^\d.]", "", s) or "0")


def _parse_bin_row(line: str) -> Optional[BinRow]:
    parts = line.split()
    if len(parts) < 6:
        return None
    try:
        sw = int(parts[0])
        hw = int(parts[1])
        count = int(parts[2])
        pct = _parse_float_pct(parts[3])
        code = int(parts[4])
        desc = parts[5]
        return BinRow(sw, hw, count, pct, code, desc)
    except (ValueError, IndexError):
        return None


def _parse_site_counter_line(line: str) -> Optional[SiteCounterRow]:
    m = re.match(
        r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)%?",
        line,
    )
    if not m:
        return None
    site, counter, pass_c, fail_c, yld = m.groups()
    return SiteCounterRow(int(site), int(counter), int(pass_c), int(fail_c), float(yld))


def _parse_die_line(line: str) -> Optional[DieRow]:
    if not line.strip().startswith("ErrorCode="):
        return None
    parts = {}
    for item in line.strip().split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k] = v
    try:
        error_code = int(parts.get("ErrorCode", 0))
        booton_raw = parts.get("booton") or parts.get("BootOn") or parts.get("bootOn") or ""
        tested_raw = parts.get("Tested") or parts.get("tested") or ""
        if booton_raw.upper() in ("PASS", "FAIL"):
            booton_raw = ""
        return DieRow(
            error_code=error_code,
            software_bin=int(parts.get("SoftwareBin", 0)),
            die_id=parts.get("DieID", ""),
            tj=parts.get("Tj", ""),
            temperature=int(parts.get("Temperature", 0)),
            site=int(parts.get("Site", 0)),
            bios_time=parts.get("BiosTime", ""),
            test_time=parts.get("TestTime", ""),
            barcode=parts.get("2DBarCode", ""),
            boot_on=error_code_to_boot_on(error_code),
            booton=booton_raw,
            tested=tested_raw,
        )
    except (ValueError, KeyError):
        return None


def parse_sum_file(path: Path) -> ParsedSum:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    meta_raw: dict = {}
    site_summaries: List[SiteSummaryBlock] = []
    total_bins: List[BinRow] = []
    site_counters: List[SiteCounterRow] = []
    dies: List[DieRow] = []

    section = None
    current_site: Optional[SiteSummaryBlock] = None
    in_total_summary = False

    for line in lines:
        stripped = line.strip()

        if "Site" in stripped and "Summary" in stripped and "Total" not in stripped:
            m = re.search(r"Site(\d+)\s+Summary", stripped)
            if m:
                current_site = SiteSummaryBlock(site_no=int(m.group(1)))
                site_summaries.append(current_site)
                section = "site_summary"
                in_total_summary = False
            continue

        if "Total Site Summary" in stripped:
            section = "total_summary"
            in_total_summary = True
            current_site = None
            continue

        if "Site Counter" in stripped and "Yield" in stripped:
            section = "site_counter"
            continue

        if "Rawdata list" in stripped:
            section = "rawdata"
            continue

        if " End " in stripped and stripped.startswith("*"):
            if in_total_summary:
                section = None
            continue

        if section is None and ":" in stripped and not stripped.startswith("*"):
            kv = _parse_meta_line(stripped)
            if kv:
                meta_raw[kv[0]] = kv[1]
            continue

        if section in ("site_summary", "total_summary"):
            if "Software" in stripped and "Hardware" in stripped:
                continue
            if "Category" in stripped:
                continue
            row = _parse_bin_row(stripped)
            if row:
                if section == "site_summary" and current_site:
                    current_site.bins.append(row)
                elif section == "total_summary":
                    total_bins.append(row)
            continue

        if section == "site_counter":
            if "Site No" in stripped:
                continue
            row = _parse_site_counter_line(line)
            if row:
                site_counters.append(row)
            continue

        if section == "rawdata":
            row = _parse_die_line(stripped)
            if row:
                dies.append(row)

    meta: dict = {}
    for raw_key, field in META_KEYS.items():
        if raw_key in meta_raw:
            val = meta_raw[raw_key]
            if field in ("traveler_qty", "input_qty", "pass_count", "fail_count", "bin", "temperature"):
                meta[field] = _parse_int(val)
            elif field == "yield_pct":
                meta[field] = _parse_float_pct(val)
            else:
                meta[field] = val

    test_mode = meta.get("test_mode", "")
    round_key, sub_batch = parse_test_mode(test_mode)

    return ParsedSum(
        meta=meta,
        test_mode=test_mode,
        round_key=round_key,
        sub_batch=sub_batch,
        site_summaries=site_summaries,
        total_bins=total_bins if total_bins else _aggregate_bins_from_sites(site_summaries),
        site_counters=site_counters,
        dies=dies,
        source_file=str(path),
    )


def _aggregate_bins_from_sites(sites: List[SiteSummaryBlock]) -> List[BinRow]:
    from collections import defaultdict

    agg: dict = defaultdict(lambda: {"count": 0, "row": None})
    total = 0
    for site in sites:
        for b in site.bins:
            key = (b.sw_category, b.hw_bin, b.code, b.description)
            agg[key]["count"] += b.count
            agg[key]["row"] = b
            total += b.count
    result = []
    for key, v in agg.items():
        b = v["row"]
        cnt = v["count"]
        pct = (cnt / total * 100) if total else 0
        result.append(BinRow(b.sw_category, b.hw_bin, cnt, pct, b.code, b.description))
    return sorted(result, key=lambda x: -x.count)
