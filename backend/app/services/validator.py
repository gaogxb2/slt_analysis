from dataclasses import dataclass
from typing import List, Optional

from app.services.round_merger import MergedRound
from app.services.types import ParsedSum, parse_round_order


@dataclass
class ValidationIssue:
    level: str  # error | warning
    code: str
    message: str
    round_key: Optional[str] = None


def validate_parsed_sum(parsed: ParsedSum) -> List[ValidationIssue]:
    issues = []
    iq = parsed.meta.get("input_qty", 0)
    p = parsed.meta.get("pass_count", 0)
    f = parsed.meta.get("fail_count", 0)
    if iq != p + f:
        issues.append(
            ValidationIssue(
                "error",
                "qty_mismatch",
                f"{parsed.test_mode}: Input QTY ({iq}) != Pass ({p}) + Fail ({f})",
                parsed.round_key,
            )
        )
    return issues


def validate_merged_round(merged: MergedRound) -> List[ValidationIssue]:
    issues = []
    die_ids = [d.die_id for d in merged.dies]
    if len(die_ids) != len(set(die_ids)):
        issues.append(
            ValidationIssue(
                "error",
                "duplicate_die",
                f"{merged.round_key}: duplicate DieID in merged round",
                merged.round_key,
            )
        )
    return issues


def validate_lot_rounds(
    rounds: List[MergedRound],
    all_parsed: List[ParsedSum],
) -> List[ValidationIssue]:
    issues = []
    for p in all_parsed:
        issues.extend(validate_parsed_sum(p))

    by_round: dict = {}
    for m in rounds:
        if m.round_key in by_round:
            continue
        by_round[m.round_key] = m
        issues.extend(validate_merged_round(m))

    sorted_keys = sorted(by_round.keys(), key=parse_round_order)
    for i in range(len(sorted_keys) - 1):
        cur = by_round[sorted_keys[i]]
        nxt = by_round[sorted_keys[i + 1]]
        if nxt.input_qty != cur.fail_count:
            issues.append(
                ValidationIssue(
                    "warning",
                    "retest_chain",
                    f"Retest chain: {nxt.round_key} input ({nxt.input_qty}) "
                    f"!= {cur.round_key} fail ({cur.fail_count})",
                    nxt.round_key,
                )
            )
        cur_fail_ids = {d.die_id for d in cur.dies if d.boot_on.upper() == "FAIL"}
        nxt_ids = {d.die_id for d in nxt.dies}
        extra = nxt_ids - cur_fail_ids
        if extra and cur_fail_ids:
            issues.append(
                ValidationIssue(
                    "warning",
                    "retest_die_mismatch",
                    f"{nxt.round_key}: {len(extra)} DieID(s) not in {cur.round_key} fail set",
                    nxt.round_key,
                )
            )

    return issues
