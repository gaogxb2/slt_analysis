#!/usr/bin/env python3
"""从 M2+1 模板生成扩展测试 SUM 文件（AB0000AA1/AC1、JZADIWHMZ 多 STAGE）。"""
import hashlib
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.sum_parser import parse_sum_file

LOGS_DIR = ROOT / "logs"
TEMPLATE = LOGS_DIR / "testsum_M2+1.SUM"


def stage_to_mode_prefix(stage: str) -> str:
    """MT1 -> M1, MT2 -> M2, MT3 -> M3"""
    m = re.match(r"MT(\d+)", stage.strip(), re.I)
    return f"M{m.group(1)}" if m else stage


def mutate_die_id(die_id: str, salt: str) -> str:
    """按批次 salt 微调 DieID，保持格式不变。"""
    parts = die_id.split()
    if len(parts) < 4:
        return die_id
    h = int(hashlib.md5(salt.encode()).hexdigest(), 16)
    p0 = int(parts[0], 16)
    parts[0] = f"{(p0 ^ (h & 0xFFFF)):04X}"
    p1 = int(parts[1], 16)
    parts[1] = f"{(p1 ^ ((h >> 8) & 0xFFFF)):04X}"
    return " ".join(parts)


def mutate_barcode(barcode: str, salt: str) -> str:
    h = int(hashlib.md5((salt + barcode).encode()).hexdigest(), 16)
    base = int(barcode) if barcode.isdigit() else int(barcode or "0")
    return str((base + (h % 900_000_000_000)) % 1_000_000_000_000).zfill(12)


def render_sum_from_template(
    parsed,
    lot_no: str,
    stage: str,
    test_mode: str,
    dies_subset: int | None = None,
    date_offset_days: int = 0,
) -> str:
    dies = parsed.dies[:dies_subset] if dies_subset else list(parsed.dies)
    pass_cnt = sum(1 for d in dies if str(d.error_code).startswith("10"))
    fail_cnt = len(dies) - pass_cnt
    input_qty = len(dies)
    yld = (pass_cnt / input_qty * 100) if input_qty else 0

    # rebuild site summaries from dies
    from collections import defaultdict
    from app.services.round_merger import _die_to_bin, _site_summaries_from_dies

    site_summaries = _site_summaries_from_dies(dies)
    site_agg: dict = defaultdict(lambda: {"counter": 0, "pass": 0, "fail": 0})
    for d in dies:
        s = site_agg[d.site]
        s["counter"] += 1
        if str(d.error_code).startswith("10"):
            s["pass"] += 1
        else:
            s["fail"] += 1

    # meta dates
    start = parsed.meta.get("start_time", "2020/02/02 01:01:01")
    if date_offset_days:
        import datetime
        dt = datetime.datetime.strptime(start, "%Y/%m/%d %H:%M:%S")
        dt += datetime.timedelta(days=date_offset_days)
        start = dt.strftime("%Y/%m/%d %H:%M:%S")
    report = start  # simplified

    lines = [
        "****TITLE xxx******",
        "",
        f"LOT NO. : {lot_no}",
        f"Mater Traveler QTY : {parsed.meta.get('traveler_qty', 100)}",
        f"Input Testing QTY : {input_qty}",
        f"START TIME : {start}",
        f"Bin : {parsed.meta.get('bin', 1)}",
        f"Total Pass: {pass_cnt}",
        f"Total Fail : {fail_cnt}",
        f"Pass Yield : {yld:.2f}%",
        f"Lot Start Date : {start}",
        f"Report Date : {report}",
        f"STAGE : {stage}",
        "",
        f"Test Mode : {test_mode}",
        "",
        f"Temperature : {parsed.meta.get('temperature', 99)}",
        "",
    ]

    for ss in site_summaries:
        lines.append(f"*****Site{ss.site_no} Summary  ******")
        lines.append("Software   Hardware    COUNT    Per(%)   Code    BinDESCRIPT")
        lines.append("Category     Bin")
        total = sum(b.count for b in ss.bins)
        for b in ss.bins:
            pct = (b.count / total * 100) if total else 0
            lines.append(
                f"{b.sw_category:<12} {b.hw_bin:<11} {b.count:<10} {pct:>6.2f}%   {b.code:<6} {b.description}"
            )
        lines.append("")

    # total bins
    bin_agg: dict = defaultdict(int)
    bin_meta: dict = {}
    for d in dies:
        b = _die_to_bin(d)
        key = (b.sw_category, b.hw_bin, b.code, b.description)
        bin_agg[key] += 1
        bin_meta[key] = b
    total_bin = sum(bin_agg.values())
    lines.append("*****Total Site Summary   ***********")
    lines.append("Software   Hardware    COUNT    Per(%)   Code    BinDESCRIPT")
    lines.append("Category     Bin")
    for key, cnt in sorted(bin_agg.items(), key=lambda x: -x[1]):
        b = bin_meta[key]
        pct = (cnt / total_bin * 100) if total_bin else 0
        lines.append(
            f"{b.sw_category:<12} {b.hw_bin:<11} {cnt:<10} {pct:>6.2f}%   {b.code:<6} {b.description}"
        )
    lines.append("************** End ******")
    lines.append("")
    lines.append("******** Site Counter / Yield *******")
    lines.append("Site No     Site Counter    Pass   Fail   Site Yield(%)")
    for site_no in sorted(site_agg.keys()):
        s = site_agg[site_no]
        y = (s["pass"] / s["counter"] * 100) if s["counter"] else 0
        lines.append(f"   {site_no:<9} {s['counter']:<14} {s['pass']:<6} {s['fail']:<6} {y:.2f}%")
    lines.append("")
    lines.append("******Rawdata list*******")

    base_dt = datetime.strptime(start, "%Y/%m/%d %H:%M:%S")
    salt = f"{lot_no}:{stage}:{test_mode}"
    for i, d in enumerate(dies):
        die_id = mutate_die_id(d.die_id, f"{salt}:{i}")
        barcode = mutate_barcode(d.barcode, f"{salt}:{i}")
        test_secs = float(re.sub(r"[^\d.]", "", d.test_time) or "1")
        boot_dt = base_dt + timedelta(seconds=i * 3)
        tested_dt = boot_dt + timedelta(seconds=max(test_secs, 1))
        ts = lambda dt: dt.strftime("%H:%M:%S-%Y/%m/%d")
        lines.append(
            f"ErrorCode={d.error_code},SoftwareBin={d.software_bin},DieID={die_id},"
            f"Tj={d.tj},Temperature={d.temperature},Site={d.site},BiosTime={d.bios_time},"
            f"TestTime={d.test_time},2DBarCode={barcode},booton={ts(boot_dt)},Tested={ts(tested_dt)}"
        )

    return "\n".join(lines) + "\n"


def clone_sum(lot_no: str, stage: str, test_mode: str, outfile: str, **kwargs) -> Path:
    parsed = parse_sum_file(TEMPLATE)
    content = render_sum_from_template(parsed, lot_no, stage, test_mode, **kwargs)
    path = LOGS_DIR / outfile
    path.write_text(content, encoding="utf-8")
    return path


def main():
    specs = [
        # 同一物料不同测试批次：AB0000A* 系列
        ("AB0000AA1", "MT1", "M1+1", "testsum_AB0000AA1_M1+1.SUM", {}),
        ("AB0000AC1", "MT3", "M3+1", "testsum_AB0000AC1_M3+1.SUM", {"date_offset_days": 2}),
        # 同一 LOT NO. 跨 STAGE：JZADIWHMZ
        ("JZADIWHMZ", "MT1", "M1+1", "testsum_JZADIWHMZ_MT1_M1+1.SUM", {"dies_subset": 18, "date_offset_days": 5}),
        ("JZADIWHMZ", "MT2", "M2+1", "testsum_JZADIWHMZ_MT2_M2+1.SUM", {"dies_subset": 20, "date_offset_days": 6}),
        ("JZADIWHMZ", "MT3", "M3+1", "testsum_JZADIWHMZ_MT3_M3+1.SUM", {"dies_subset": 15, "date_offset_days": 7}),
    ]
    for lot_no, stage, mode, fname, opts in specs:
        p = clone_sum(lot_no, stage, mode, fname, **opts)
        print(f"written {p.name}")


if __name__ == "__main__":
    main()
