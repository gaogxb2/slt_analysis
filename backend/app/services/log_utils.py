import re
from pathlib import Path


def normalize_die_id(die_id: str) -> str:
    return re.sub(r"\s+", "", die_id or "").upper()


def normalize_test_time(value: str) -> str:
    """Normalize test time strings for comparison."""
    if not value:
        return ""
    s = value.strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if s.endswith("s") and not s.endswith(" ms"):
        s = s[:-1].strip()
    return s


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
