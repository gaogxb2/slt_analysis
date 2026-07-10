import re
from pathlib import Path
from typing import Optional

from app.services.types import DieIdGroup, OneTestRow, ParsedLog, parse_test_mode


def _parse_kv(line: str) -> Optional[tuple[str, str]]:
    m = re.match(r"^(.+?)\s*:\s*(.*)$", line.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2).strip()


def _section_tag(line: str) -> Optional[str]:
    """区块标记容错：忽略标记内多余空格与大小写。"""
    compact = re.sub(r"\s+", "", line.strip().upper())
    mapping = {
        "[BEGIN]": "begin",
        "[ONETEST]": "onetest",
        "[ONETESTEND]": "onetest_end",
        "[CHIPINFO]": "chipinfo",
        "[CHIPEND]": "chip_end",
    }
    return mapping.get(compact)


def _chipinfo_key(raw_key: str) -> str:
    """键名容错：DIE ID STR / DIE_ID_STR → DIEID_STR。"""
    compact = re.sub(r"[\s_]+", "", raw_key.upper())
    aliases = {
        "SOFTBIN": "SOFT_BIN",
        "PF": "P_F",
        "TESTTIME": "TEST_TIME",
        "TESTSTART": "TEST_START",
        "DIEIDSTR": "DIEID_STR",
        "DIEIDNAME": "DIEID_NAME",
        "DIEIDLOT": "DIEID_LOT",
        "DIEIDWAFER": "DIEID_WAFER",
        "DIEIDX": "DIEID_X",
        "DIEIDY": "DIEID_Y",
    }
    return aliases.get(compact, raw_key.upper().replace(" ", "_"))


_CHIPINFO_FIELD_KEYS = frozenset({
    "SOFT_BIN", "P_F", "TEST_TIME", "TEST_START",
    "DIEID_STR", "DIEID_NAME", "DIEID_LOT", "DIEID_WAFER", "DIEID_X", "DIEID_Y",
})


def _append_die_group(current_die: dict, die_groups: list[DieIdGroup]) -> None:
    if not current_die.get("DIEID_STR"):
        return
    die_groups.append(
        DieIdGroup(
            die_id_str=current_die.get("DIEID_STR", ""),
            die_id_name=current_die.get("DIEID_NAME", ""),
            die_id_lot=current_die.get("DIEID_LOT", ""),
            die_id_wafer=current_die.get("DIEID_WAFER", ""),
            die_id_x=current_die.get("DIEID_X", ""),
            die_id_y=current_die.get("DIEID_Y", ""),
        )
    )


def _apply_chipinfo_kv(
    key: str,
    val: str,
    chipinfo: dict,
    current_die: dict,
    die_groups: list[DieIdGroup],
) -> None:
    if key == "SOFT_BIN":
        chipinfo["SOFT_BIN"] = _parse_int(val)
    elif key == "P_F":
        chipinfo["P_F"] = val.upper()
    elif key == "TEST_TIME":
        chipinfo["TEST_TIME"] = val
    elif key == "TEST_START":
        chipinfo["TEST_START"] = val
    elif key == "DIEID_STR":
        if current_die.get("DIEID_STR"):
            _append_die_group(current_die, die_groups)
            current_die.clear()
        current_die["DIEID_STR"] = val
    elif key == "DIEID_NAME":
        current_die["DIEID_NAME"] = val
    elif key == "DIEID_LOT":
        current_die["DIEID_LOT"] = val
    elif key == "DIEID_WAFER":
        current_die["DIEID_WAFER"] = val
    elif key == "DIEID_X":
        current_die["DIEID_X"] = val
    elif key == "DIEID_Y":
        current_die["DIEID_Y"] = val


def _parse_int(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s) or "0")


def _extract_barcode_from_filename(path: Path) -> Optional[str]:
    """{LOT}_S{site}_{die}_{barcode}.log"""
    stem = path.stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) >= 10:
        return parts[1]
    return None


def validate_chip_pf(onetests: list[OneTestRow], chip_pf: str) -> bool:
    if not onetests:
        return True
    any_fail = any(t.pf.upper() == "F" for t in onetests)
    expected = "F" if any_fail else "P"
    return chip_pf.upper() == expected


def parse_testlog_file(path: Path) -> ParsedLog:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    header: dict = {}
    onetests: list[OneTestRow] = []
    die_groups: list[DieIdGroup] = []
    chipinfo: dict = {}
    current_onetest: dict = {}
    section = None
    in_onetest = False
    current_die: dict = {}

    for line in lines:
        stripped = line.strip()
        tag = _section_tag(stripped)
        if tag == "begin":
            section = "begin"
            continue
        if tag == "onetest":
            in_onetest = True
            current_onetest = {}
            continue
        if tag == "onetest_end":
            if current_onetest:
                onetests.append(
                    OneTestRow(
                        test_txt=current_onetest.get("TEST_TXT", ""),
                        pattern=current_onetest.get("PATTERN", ""),
                        result=current_onetest.get("RESULT", ""),
                        pf=current_onetest.get("P_F", "P").upper(),
                        test_time_ms=_parse_int(current_onetest.get("TEST_TIME", "0")),
                    )
                )
            in_onetest = False
            current_onetest = {}
            continue
        if tag == "chipinfo":
            section = "chipinfo"
            continue
        if tag == "chip_end":
            _append_die_group(current_die, die_groups)
            current_die.clear()
            break

        if in_onetest:
            kv = _parse_kv(stripped)
            if kv:
                key = kv[0].replace(" ", "_").upper()
                if key == "TEST_TXT":
                    current_onetest["TEST_TXT"] = kv[1]
                elif key == "PATTERN":
                    current_onetest["PATTERN"] = kv[1]
                elif key == "RESULT":
                    current_onetest["RESULT"] = kv[1]
                elif key in ("P_F", "PF"):
                    current_onetest["P_F"] = kv[1]
                elif key == "TEST_TIME":
                    current_onetest["TEST_TIME"] = kv[1]
            continue

        kv = _parse_kv(stripped)
        if not kv:
            continue

        if section == "begin":
            header[kv[0].upper()] = kv[1]
            chip_key = _chipinfo_key(kv[0])
            if chip_key in _CHIPINFO_FIELD_KEYS:
                section = "chipinfo"
                _apply_chipinfo_kv(chip_key, kv[1], chipinfo, current_die, die_groups)
            continue

        if section == "chipinfo":
            chip_key = _chipinfo_key(kv[0])
            _apply_chipinfo_kv(chip_key, kv[1], chipinfo, current_die, die_groups)

    _append_die_group(current_die, die_groups)

    lot_no = header.get("CUSTOMER LOT ID", header.get("CUSTOMER_LOT_ID", ""))
    stage = header.get("TEST STAGE", header.get("TEST_STAGE", ""))
    test_flow = header.get("TEST FLOW", header.get("TEST_FLOW", ""))
    test_start = header.get("TEST START", header.get("TEST_START", ""))
    site = _parse_int(header.get("TEST SITE", header.get("TEST_SITE", "0")))
    round_key, sub_batch = parse_test_mode(test_flow)

    barcode = _extract_barcode_from_filename(path)

    return ParsedLog(
        lot_no=lot_no,
        site=site,
        stage=stage,
        test_flow=test_flow,
        round_key=round_key,
        sub_batch=sub_batch,
        test_start=test_start,
        onetests=onetests,
        soft_bin=chipinfo.get("SOFT_BIN", 0),
        chip_pf=chipinfo.get("P_F", ""),
        chip_test_time=chipinfo.get("TEST_TIME", ""),
        chip_test_start=chipinfo.get("TEST_START", test_start),
        die_id_groups=die_groups,
        barcode=barcode,
        source_file=str(path),
    )
