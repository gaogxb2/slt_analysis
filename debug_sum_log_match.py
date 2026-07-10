#!/usr/bin/env python3
"""SUM ↔ Log 匹配调试：解析 logs 目录内 SUM/Log，输出匹配详情到根目录。

用法:
  python debug_sum_log_match.py              # 默认扫描 ./logs
  python debug_sum_log_match.py /path/to/logs
  python debug_sum_log_match.py --out my_debug.log

输出文件（默认）: <项目根>/sum_log_match_debug.log
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.log_utils import normalize_die_id, primary_die_id  # noqa: E402
from app.services.sum_parser import parse_sum_file  # noqa: E402
from app.services.testlog_parser import parse_testlog_file  # noqa: E402

DEFAULT_LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_OUT = PROJECT_ROOT / "sum_log_match_debug.log"

@dataclass
class SumDieRow:
    source_file: str
    lot_no: str
    stage: str
    test_mode: str
    round_key: str
    site: int
    die_id_raw: str
    primary_die_id: str
    barcode: str

    @property
    def lot_key(self) -> tuple[str, str]:
        return (self.lot_no, self.stage)

    def match_key(self) -> tuple:
        return (self.round_key, self.test_mode, self.site, self.primary_die_id)

    def fallback_key(self) -> tuple:
        return (self.round_key, self.site, self.primary_die_id)


@dataclass
class LogRow:
    source_file: str
    lot_no: str
    stage: str
    test_flow: str
    round_key: str
    site: int
    die_id_raw: str
    primary_die_id: str
    barcode: str
    pf: str = ""

    @property
    def lot_key(self) -> tuple[str, str]:
        return (self.lot_no, self.stage)

    def match_key(self) -> tuple:
        return (self.round_key, self.test_flow, self.site, self.primary_die_id)

    def fallback_key(self) -> tuple:
        return (self.round_key, self.site, self.primary_die_id)


@dataclass
class FieldCheck:
    field: str
    sum_value: str
    log_value: str
    ok: bool


def _log(out: IO[str], line: str = "") -> None:
    out.write(line + "\n")
    print(line)


def _field_checks(s: SumDieRow, lg: LogRow) -> List[FieldCheck]:
    pairs = [
        ("lot_no", s.lot_no, lg.lot_no),
        ("stage", s.stage, lg.stage),
        ("round_key", s.round_key, lg.round_key),
        ("test_mode", s.test_mode, lg.test_flow),
        ("site", str(s.site), str(lg.site)),
        ("primary_die_id", s.primary_die_id, lg.primary_die_id),
    ]
    return [
        FieldCheck(name, sv, lv, sv == lv)
        for name, sv, lv in pairs
    ]


def _fmt_checks(checks: List[FieldCheck]) -> str:
    parts = []
    for c in checks:
        mark = "OK" if c.ok else "FAIL"
        parts.append(f"{c.field}={c.sum_value!r} vs {c.log_value!r} [{mark}]")
    return " | ".join(parts)


def _load_sum_rows(directory: Path, out: IO[str]) -> List[SumDieRow]:
    rows: List[SumDieRow] = []
    sum_files = sorted(directory.rglob("*.SUM"))
    _log(out, f"=== SUM 文件 ({len(sum_files)}) ===")
    for path in sum_files:
        rel = path.relative_to(directory)
        try:
            parsed = parse_sum_file(path)
        except Exception as e:
            _log(out, f"  [解析失败] {rel}: {e}")
            continue
        lot_no = parsed.meta.get("lot_no", "")
        stage = parsed.meta.get("stage", "")
        _log(
            out,
            f"  {rel}: LOT={lot_no!r} STAGE={stage!r} TestMode={parsed.test_mode!r} "
            f"round_key={parsed.round_key!r} dies={len(parsed.dies)}",
        )
        for d in parsed.dies:
            rows.append(
                SumDieRow(
                    source_file=str(rel),
                    lot_no=lot_no,
                    stage=stage,
                    test_mode=parsed.test_mode,
                    round_key=parsed.round_key,
                    site=d.site,
                    die_id_raw=d.die_id,
                    primary_die_id=primary_die_id(d.die_id),
                    barcode=d.barcode or "",
                )
            )
    _log(out, f"SUM 芯片记录合计: {len(rows)}")
    return rows


def _load_log_rows(directory: Path, out: IO[str]) -> List[LogRow]:
    rows: List[LogRow] = []
    log_files = sorted(directory.rglob("*.log"))
    _log(out, f"\n=== Log 文件 ({len(log_files)}) ===")
    for path in log_files:
        rel = path.relative_to(directory)
        try:
            parsed = parse_testlog_file(path)
        except Exception as e:
            _log(out, f"  [解析失败] {rel}: {e}")
            continue
        die_raw = ""
        if parsed.die_id_groups:
            die_raw = parsed.die_id_groups[0].die_id_str
        primary = normalize_die_id(die_raw)
        _log(
            out,
            f"  {rel}: LOT={parsed.lot_no!r} STAGE={parsed.stage!r} FLOW={parsed.test_flow!r} "
            f"round_key={parsed.round_key!r} SITE={parsed.site} "
            f"DIEID_STR={die_raw!r} primary={primary!r} P_F={parsed.chip_pf!r}",
        )
        if len(parsed.die_id_groups) > 1:
            extras = [g.die_id_str for g in parsed.die_id_groups[1:]]
            _log(out, f"    附加 DIEID_STR: {extras}")
        if not parsed.lot_no:
            _log(out, "    [警告] 缺少 CUSTOMER LOT ID")
        if not die_raw:
            _log(out, "    [警告] 缺少第一组 DIEID_STR（解析结果为空）")
            chip_lines = []
            markers: list[str] = []
            in_chip = False
            try:
                for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = ln.strip()
                    compact = re.sub(r"\s+", "", s.upper())
                    if compact in ("[CHIPINFO]", "[CHIPEND]"):
                        markers.append(s)
                    if compact == "[CHIPINFO]":
                        in_chip = True
                    if in_chip and ("DIEID" in s.upper() or compact == "[CHIPEND]"):
                        chip_lines.append(ln.rstrip())
                    if compact == "[CHIPEND]":
                        break
            except OSError:
                pass
            if markers:
                _log(out, f"    检测到区块标记: {markers}")
                compact_markers = [re.sub(r"\s+", "", m.upper()) for m in markers]
                if "[CHIPEND]" in compact_markers:
                    _log(out, "    [提示] 若结束标记为 [CHIPEND]（无空格），需使用最新版解析器")
            if chip_lines:
                _log(out, "    [CHIPINFO 相关原始行]")
                for ln in chip_lines[:12]:
                    _log(out, f"      {ln}")
            else:
                _log(out, "    未找到 [CHIPINFO] 区块或 DIEID_STR 行")
        rows.append(
            LogRow(
                source_file=str(rel),
                lot_no=parsed.lot_no,
                stage=parsed.stage,
                test_flow=parsed.test_flow,
                round_key=parsed.round_key,
                site=parsed.site,
                die_id_raw=die_raw,
                primary_die_id=primary,
                barcode=parsed.barcode or "",
                pf=parsed.chip_pf or "",
            )
        )
    _log(out, f"Log 记录合计: {len(rows)}")
    return rows


def _find_log_for_sum(
    s: SumDieRow,
    logs: List[LogRow],
) -> tuple[Optional[LogRow], str, List[tuple[LogRow, List[FieldCheck]]]]:
    """返回 (匹配 log, 匹配方式 full|fallback|None, 同 LOT 候选及字段对比)."""
    same_lot = [lg for lg in logs if lg.lot_key == s.lot_key]
    candidates: List[tuple[LogRow, List[FieldCheck]]] = []

    for lg in same_lot:
        checks = _field_checks(s, lg)
        candidates.append((lg, checks))

    for lg in same_lot:
        if lg.match_key() == s.match_key():
            return lg, "full", candidates

    for lg in same_lot:
        if lg.fallback_key() == s.fallback_key():
            return lg, "fallback", candidates

    return None, "none", candidates


def _find_sum_for_log(
    lg: LogRow,
    sums: List[SumDieRow],
) -> tuple[Optional[SumDieRow], str]:
    same_lot = [s for s in sums if s.lot_key == lg.lot_key]
    for s in same_lot:
        if s.match_key() == lg.match_key():
            return s, "full"
    for s in same_lot:
        if s.fallback_key() == lg.fallback_key():
            return s, "fallback"
    return None, "none"


def run_debug(directory: Path, out_path: Path) -> None:
    directory = directory.resolve()
    with out_path.open("w", encoding="utf-8") as out:
        _log(out, "=" * 72)
        _log(out, "SUM ↔ Log 匹配调试报告")
        _log(out, f"时间: {datetime.now().isoformat(timespec='seconds')}")
        _log(out, f"扫描目录: {directory}")
        _log(out, f"匹配键: (round_key, test_mode, site, primary_die_id)")
        _log(out, f"兜底键: (round_key, site, primary_die_id) — 忽略 test_mode")
        _log(out, f"LOT 级: (lot_no, stage) 必须一致")
        _log(out, "=" * 72)

        sum_rows = _load_sum_rows(directory, out)
        log_rows = _load_log_rows(directory, out)

        _log(out, "\n" + "=" * 72)
        _log(out, "=== SUM 芯片 → Log 匹配结果 ===")
        matched_full = matched_fb = sum_only = 0

        for i, s in enumerate(sum_rows, 1):
            lg, mode, candidates = _find_log_for_sum(s, log_rows)
            _log(out, f"\n--- SUM #{i} ---")
            _log(out, f"  文件: {s.source_file}")
            _log(out, f"  LOT={s.lot_no!r} STAGE={s.stage!r} TestMode={s.test_mode!r} "
                 f"round_key={s.round_key!r} Site={s.site}")
            _log(out, f"  DieID(raw)={s.die_id_raw!r} primary={s.primary_die_id!r}")
            if s.barcode:
                _log(out, f"  2DBarCode={s.barcode!r} (不参与匹配)")

            if lg and mode == "full":
                matched_full += 1
                _log(out, f"  [匹配成功] mode=full → Log: {lg.source_file}")
            elif lg and mode == "fallback":
                matched_fb += 1
                _log(out, f"  [匹配成功] mode=fallback(test_mode 不一致但 round/site/die 一致)")
                _log(out, f"    → Log: {lg.source_file}")
                _log(out, f"    {_fmt_checks(_field_checks(s, lg))}")
            else:
                sum_only += 1
                _log(out, "  [匹配失败] 未找到 Log (UI 将显示「无 Log」)")
                if not candidates:
                    _log(out, f"    同 LOT+STAGE ({s.lot_no!r},{s.stage!r}) 下无任何 Log 文件")
                    # 跨 lot 同 die
                    cross = [lg for lg in log_rows if lg.primary_die_id == s.primary_die_id]
                    if cross:
                        _log(out, f"    但其他 LOT/STAGE 有相同 primary_die_id 的 Log ({len(cross)} 个):")
                        for lg in cross[:5]:
                            _log(out, f"      {lg.source_file}: LOT={lg.lot_no!r} STAGE={lg.stage!r} "
                                 f"FLOW={lg.test_flow!r} SITE={lg.site}")
                    else:
                        _log(out, "    全目录也无相同 primary_die_id 的 Log")
                else:
                    _log(out, f"    同 LOT+STAGE 下有 {len(candidates)} 个 Log，字段对比如下:")
                    for lg, checks in candidates:
                        failed = [c.field for c in checks if not c.ok]
                        _log(out, f"      Log: {lg.source_file}")
                        _log(out, f"        {_fmt_checks(checks)}")
                        if failed:
                            _log(out, f"        不一致字段: {', '.join(failed)}")

        _log(out, "\n" + "=" * 72)
        _log(out, "=== Log → SUM 匹配结果 ===")
        log_matched = log_unmatched = 0

        for i, lg in enumerate(log_rows, 1):
            s, mode = _find_sum_for_log(lg, sum_rows)
            _log(out, f"\n--- Log #{i} ---")
            _log(out, f"  文件: {lg.source_file}")
            _log(out, f"  LOT={lg.lot_no!r} STAGE={lg.stage!r} FLOW={lg.test_flow!r} "
                 f"round_key={lg.round_key!r} SITE={lg.site} primary={lg.primary_die_id!r}")

            if s:
                log_matched += 1
                _log(out, f"  [匹配成功] mode={mode} → SUM: {s.source_file} "
                     f"(Site={s.site} DieID={s.die_id_raw!r})")
                if mode == "fallback":
                    _log(out, f"    {_fmt_checks(_field_checks(s, lg))}")
            else:
                log_unmatched += 1
                _log(out, "  [匹配失败] 未找到对应 SUM 芯片记录")
                same_lot_sums = [x for x in sum_rows if x.lot_key == lg.lot_key]
                if not same_lot_sums:
                    _log(out, f"    无 LOT+STAGE=({lg.lot_no!r},{lg.stage!r}) 的 SUM 文件")
                else:
                    near = [x for x in same_lot_sums if x.primary_die_id == lg.primary_die_id]
                    if near:
                        _log(out, f"    同 LOT 有 {len(near)} 条相同 primary_die_id 的 SUM，但 test_mode/site/round 不符:")
                        for x in near[:5]:
                            _log(out, f"      {x.source_file}: TestMode={x.test_mode!r} "
                                 f"round_key={x.round_key!r} Site={x.site}")
                            _log(out, f"        {_fmt_checks(_field_checks(x, lg))}")
                    else:
                        _log(out, f"    同 LOT 有 {len(same_lot_sums)} 条 SUM，但 primary_die_id 均不同")

        _log(out, "\n" + "=" * 72)
        _log(out, "=== 汇总 ===")
        _log(out, f"SUM 芯片: {len(sum_rows)}  |  匹配(full): {matched_full}  |  "
             f"匹配(fallback): {matched_fb}  |  无 Log: {sum_only}")
        _log(out, f"Log 文件: {len(log_rows)}  |  有 SUM: {log_matched}  |  无 SUM: {log_unmatched}")
        _log(out, "=" * 72)
        _log(out, f"\n报告已写入: {out_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SUM ↔ Log 匹配调试，输出到项目根目录")
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(DEFAULT_LOGS_DIR),
        help=f"扫描目录（默认 {DEFAULT_LOGS_DIR}）",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"输出日志路径（默认 {DEFAULT_OUT}）",
    )
    args = parser.parse_args()
    run_debug(Path(args.directory), Path(args.out))


if __name__ == "__main__":
    main()
