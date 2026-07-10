#!/usr/bin/env python3
"""将 SUM Rawdata 中 BootOn=PASS/FAIL 转为 booton/Tested 时间戳格式。"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT / "logs"

RAW_LINE = re.compile(
    r"^ErrorCode=(\d+),(.+?),BootOn=(PASS|FAIL)\s*$",
    re.IGNORECASE,
)


def _parse_base_dt(meta_lines: list[str]) -> datetime:
    for key in ("Report Date", "START TIME", "Lot Start Date"):
        for line in meta_lines:
            if line.strip().startswith(key):
                val = line.split(":", 1)[1].strip()
                for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(val, fmt)
                    except ValueError:
                        continue
    return datetime(2026, 1, 1, 13, 13, 13)


def _fmt_ts(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S-%Y/%m/%d")


def _test_seconds(test_time: str) -> float:
    try:
        return float(re.sub(r"[^\d.]", "", test_time) or "1")
    except ValueError:
        return 1.0


def convert_sum_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    meta_lines = [ln for ln in lines if ":" in ln and not ln.strip().startswith("ErrorCode=")]
    base = _parse_base_dt(meta_lines)
    changed = False
    idx = 0
    out_lines = []
    for line in lines:
        m = RAW_LINE.match(line.strip())
        if not m:
            out_lines.append(line)
            continue
        error_code, middle, _boot = m.groups()
        test_time_m = re.search(r"TestTime=([^,]+)", middle)
        test_secs = _test_seconds(test_time_m.group(1) if test_time_m else "1")
        boot_dt = base + timedelta(seconds=idx * 3)
        tested_dt = boot_dt + timedelta(seconds=max(test_secs, 1))
        idx += 1
        out_lines.append(
            f"ErrorCode={error_code},{middle},booton={_fmt_ts(boot_dt)},Tested={_fmt_ts(tested_dt)}"
        )
        changed = True
    if changed:
        path.write_text("\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    return changed


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else LOGS_DIR
    files = sorted(target.rglob("*.SUM"))
    n = 0
    for f in files:
        if convert_sum_file(f):
            n += 1
            print(f"updated: {f.relative_to(ROOT)}")
    print(f"done: {n}/{len(files)} files updated")


if __name__ == "__main__":
    main()
