import re
from pathlib import Path


def normalize_die_id(die_id: str) -> str:
    return re.sub(r"\s+", "", die_id or "").upper()


def primary_die_id(die_id: str) -> str:
    """取分号前的第一个 DieID 并规范化，用于 SUM↔Log 对账匹配。"""
    if not die_id:
        return ""
    first = die_id.split(";")[0].strip()
    return normalize_die_id(first)


def normalize_test_time(value: str) -> str:
    """Normalize test time strings for comparison."""
    if not value:
        return ""
    s = value.strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if s.endswith("s") and not s.endswith(" ms"):
        s = s[:-1].strip()
    return s


def error_code_is_pass(error_code: int) -> bool:
    """ErrorCode 以 10 开头为 Pass，否则 Fail。"""
    return str(error_code).startswith("10")


def error_code_to_boot_on(error_code: int) -> str:
    return "PASS" if error_code_is_pass(error_code) else "FAIL"


def boot_on_to_pf(boot_on: str) -> str:
    if not boot_on:
        return ""
    b = boot_on.strip().upper()
    if b == "PASS":
        return "P"
    if b == "FAIL":
        return "F"
    return b[:1]


def pf_match(sum_boot_on: str, log_pf: str) -> bool:
    return boot_on_to_pf(sum_boot_on) == (log_pf or "").strip().upper()[:1]
