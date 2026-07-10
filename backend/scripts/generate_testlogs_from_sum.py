#!/usr/bin/env python3
"""从 logs/**/*.SUM 批量生成每颗芯片的 testlog 文件。"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.sum_parser import parse_sum_file

LOGS_DIR = ROOT / "logs"
OUT_DIR = LOGS_DIR

ONETEST_NAMES = ("AAA_TEST", "BBB_TEST")

ERROR_DESC = {
    4000: "E2",
    4001: "E3",
    4002: "E1",
}


def sum_time_to_log_time(s: str) -> str:
    """2020/02/02 10:00:01 -> 2020/02/02_10:00:01"""
    return s.strip().replace(" ", "_", 1) if s else ""


def die_compact(die_id: str) -> str:
    return die_id.replace(" ", "")


def derive_wafer_info(die_id: str, lot_no: str) -> dict:
    h = int(hashlib.md5(die_id.encode()).hexdigest(), 16)
    return {
        "lot": lot_no[:6] if len(lot_no) >= 6 else lot_no,
        "wafer": str(1 + h % 25),
        "x": str(h % 100),
        "y": str((h // 100) % 100),
    }


def second_die_id(primary: str) -> str:
    parts = primary.split()
    if len(parts) >= 4:
        p0 = parts[0]
        alt = f"{int(p0, 16) ^ 0x00FF:04X}" + " " + " ".join(parts[1:])
        return alt
    return primary + " ALT"


def parse_test_time_seconds(raw: str) -> float:
    raw = raw.strip().rstrip("s")
    try:
        return float(raw)
    except ValueError:
        return 30.0


def build_onetests(boot_on: str, error_code: int) -> list[dict]:
    is_pass = boot_on.upper() == "PASS"
    tests = []
    for i, name in enumerate(ONETEST_NAMES):
        if is_pass:
            pf, result = "P", "0x1"
        else:
            # 第一项 Pass，第二项 Fail（任一项 Fail 则 CHIP Fail）
            if i == 0:
                pf, result = "P", "0x1"
            else:
                pf, result = "F", f"0x{error_code:X}"
        tests.append({
            "TEST_TXT": name,
            "PATTERN": "",
            "RESULT": result,
            "P_F": pf,
            "TEST_TIME": 15200 if i == 0 else 14800,
        })
    return tests


def die_id_groups(die_id: str, lot_no: str, barcode: str) -> list[dict]:
    w = derive_wafer_info(die_id, lot_no)
    compact = die_compact(die_id)
    groups = [{
        "DIEID_STR": die_id,
        "DIEID_NAME": f"DIE_{compact[:8]}",
        "DIEID_LOT": w["lot"],
        "DIEID_WAFER": w["wafer"],
        "DIEID_X": w["x"],
        "DIEID_Y": w["y"],
    }]
    # 约 35% 芯片有第二个 DieID
    h = int(hashlib.md5(barcode.encode()).hexdigest(), 16)
    if h % 100 < 35:
        alt = second_die_id(die_id)
        w2 = derive_wafer_info(alt, lot_no)
        groups.append({
            "DIEID_STR": alt,
            "DIEID_NAME": f"DIE_{die_compact(alt)[:8]}_ALT",
            "DIEID_LOT": w2["lot"],
            "DIEID_WAFER": w2["wafer"],
            "DIEID_X": w2["x"],
            "DIEID_Y": w2["y"],
        })
    return groups


def render_log(
    lot_no: str,
    site: int,
    stage: str,
    test_flow: str,
    test_start: str,
    die,
) -> str:
    boot = die.boot_on.upper()
    pf = "P" if boot == "PASS" else "F"
    onetests = build_onetests(die.boot_on, die.error_code)
    total_sec = parse_test_time_seconds(die.test_time)
    groups = die_id_groups(die.die_id, lot_no, die.barcode)
    log_start = sum_time_to_log_time(test_start)

    lines = [
        "[BEGIN]",
        "**************",
        "",
        f"CUSTOMER LOT ID     : {lot_no}",
        f"TEST SITE    : {site}",
        "",
        f"TEST STAGE   : {stage}",
        "",
        f"Test FLOW   : {test_flow}",
        "",
        f"TEST START     : {log_start}",
        "*********************",
        "",
    ]

    for t in onetests:
        lines.extend([
            "[ONETEST]",
            f"TEST_TXT : {t['TEST_TXT']}",
            f"PATTERN : {t['PATTERN']}",
            f"RESULT :{t['RESULT']}",
            f"P_F    :{t['P_F']}",
            f"TEST_TIME : {t['TEST_TIME']}",
            "[ONETEST END]",
            "",
        ])

    lines.append("[CHIPINFO]")
    lines.append(f"SOFT_BIN: {die.software_bin}")
    lines.append(f"P_F     :{pf}")
    lines.append(f"TEST_TIME   :{total_sec}s")
    lines.append(f"TEST_START  :{log_start}")
    for g in groups:
        lines.append(f"DIEID_STR   : {g['DIEID_STR']}")
        lines.append(f"DIEID_NAME   : {g['DIEID_NAME']}")
        lines.append(f"DIEID_LOT   : {g['DIEID_LOT']}")
        lines.append(f"DIEID_WAFER : {g['DIEID_WAFER']}")
        lines.append(f"DIEID_X   : {g['DIEID_X']}")
        lines.append(f"DIEID_Y : {g['DIEID_Y']}")
    lines.append("[CHIP END]")
    return "\n".join(lines) + "\n"


def should_skip_sum(path: Path) -> bool:
    if path.name.lower() == "testsum.sum":
        # 与 testsum_M2+1.SUM 内容重复
        return True
    return False


def main():
    sum_files = sorted(LOGS_DIR.rglob("*.SUM"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    total_logs = 0
    seen_modes: set[tuple[str, str]] = set()

    for path in sum_files:
        if should_skip_sum(path):
            print(f"skip duplicate: {path.name}")
            continue

        parsed = parse_sum_file(path)
        lot_no = parsed.meta.get("lot_no", "UNKNOWN")
        stage = parsed.meta.get("stage", "MT2")
        test_flow = parsed.test_mode
        test_start = parsed.meta.get("start_time", "")

        mode_key = (lot_no, test_flow)
        out_sub = OUT_DIR / test_flow
        out_sub.mkdir(parents=True, exist_ok=True)

        for die in parsed.dies:
            fname = f"{lot_no}_S{die.site}_{die_compact(die.die_id)}_{die.barcode}.log"
            fname = re.sub(r"[^\w.\-+]", "_", fname)
            out_path = out_sub / fname
            content = render_log(lot_no, die.site, stage, test_flow, test_start, die)
            out_path.write_text(content, encoding="utf-8")
            total_logs += 1

        seen_modes.add(mode_key)
        print(f"{path.name}: {len(parsed.dies)} logs -> {out_sub.relative_to(ROOT)}")

    print(f"\nTotal: {total_logs} log files in {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
