"""hwpx_resume_supplement — 이력서 사실값으로 HWPX 표·체크·서명 칸 보강(RHWP).

cross_form/hwpx_fill 이 못 채우는 **좌표형 표**(학력·자격·경력)와
폼 checkBtn(모집분야), 서명일을 **이력서에서 추출한 사실**만 기입한다.
날조 0 — 호출자가 넘긴 facts 만 사용.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from .hwpx_fill import _HP, _direct, _direct_form_checkbtns, _q, _same_file, _strip_linesegarray

_STANDALONE_RE = __import__("re").compile(rb"standalone\s*=\s*['\"](yes|no)['\"]")


@dataclass
class ResumeSupplementReport:
    input: str
    output: str = ""
    ok: bool = False
    tables_filled: list[str] = field(default_factory=list)
    checks_set: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input": self.input,
            "output": self.output,
            "ok": self.ok,
            "tables_filled": self.tables_filled,
            "checks_set": self.checks_set,
            "notes": self.notes,
        }


def _detect_standalone(xml_bytes: bytes) -> Optional[bool]:
    m = _STANDALONE_RE.search(xml_bytes[:200])
    if not m:
        return None
    return m.group(1) == b"yes"


def _set_tc_text(tc, text: str) -> bool:
    """값 칸 hp:t 만 설정(라벨 run 보존). 빈칸/공백/플레이스홀더만."""
    from .hwpx_fill import _cell_text

    cur = _cell_text(tc).strip()
    if cur and cur not in {"~", "(yyyy/mm/dd)", "( )"} and not cur.startswith("(yyyy"):
        return False
    for t in tc.iter(_q("t")):
        if t.text is None or not str(t.text).strip() or str(t.text).strip() in {
            "~", "(yyyy/mm/dd)", "( )", " ",
        }:
            t.text = text
            parent = t.getparent()
            while parent is not None:
                if str(parent.tag).endswith("tc"):
                    _strip_linesegarray(parent)
                    break
                parent = parent.getparent()
            return True
    run = etree.Element(_q("run"))
    run.set("charPrIDRef", "0")
    t = etree.SubElement(run, _q("t"))
    t.text = text
    sub = tc.find(".//{%s}subList" % _HP)
    if sub is None:
        return False
    p = sub.find("{%s}p" % _HP)
    if p is None:
        p = etree.SubElement(sub, _q("p"))
    p.append(run)
    _strip_linesegarray(tc)
    return True


def _find_tbl_by_snippet(root, snippet: str):
    for tbl in root.iter(_q("tbl")):
        blob = "".join(tbl.itertext())
        if snippet in blob:
            return tbl
    return None


def _tc_at(tbl, col: int, row: int):
    for tr in _direct(tbl, "tr"):
        for tc in _direct(tr, "tc"):
            addr = tc.find(_q("cellAddr"))
            if addr is not None and int(addr.get("colAddr", -1)) == col and int(
                addr.get("rowAddr", -1)
            ) == row:
                return tc
    return None


def _check_btn(tbl, col: int, row: int) -> bool:
    tc = _tc_at(tbl, col, row)
    if tc is None:
        return False
    btns = _direct_form_checkbtns(tc)
    if len(btns) != 1:
        return False
    if btns[0].get("value") != "CHECKED":
        btns[0].set("value", "CHECKED")
        return True
    return False


def supplement_hwpx_from_resume(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    *,
    education: list[tuple[str, str, str]],
    licenses: list[tuple[str, str, str, str]],
    careers: list[tuple[str, str, str, str]],
    specialty_text: str = "",
    check_columns: Optional[list[tuple[int, int, str]]] = None,
    sign_date: str = "",
    sign_name: str = "",
) -> ResumeSupplementReport:
    """이력서 표 사실을 HWPX 신청서 표에 좌표 기입."""
    src, dst = Path(in_hwpx), Path(out_hwpx)
    rep = ResumeSupplementReport(input=str(src), output=str(dst))
    if not src.is_file():
        rep.notes.append("입력 없음")
        return rep
    in_place = _same_file(src, dst)
    if in_place:
        dst = src.with_suffix(src.suffix + ".sup.part")
        rep.output = str(out_hwpx)

    check_columns = check_columns or []
    dst.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src, "r") as zin:
        names = zin.namelist()
        data = {n: zin.read(n) for n in names}

    sec_name = "Contents/section0.xml"
    if sec_name not in data:
        rep.notes.append("section0 없음")
        return rep

    root = etree.fromstring(data[sec_name])
    changed = False

    tbl_app = _find_tbl_by_snippet(root, "전문상담위원 참여 신청서")
    if tbl_app is not None:
        for col, row, label in check_columns:
            if _check_btn(tbl_app, col, row):
                rep.checks_set.append(label)
                changed = True
        if specialty_text:
            tc = _tc_at(tbl_app, 3, 7)
            if tc is not None and _set_tc_text(tc, specialty_text):
                rep.tables_filled.append("모집분야_세부")
                changed = True

    tbl_edu = _find_tbl_by_snippet(root, "학력사항")
    if tbl_edu is None:
        tbl_edu = root.findall(".//{%s}tbl" % _HP)[6] if len(root.findall(".//{%s}tbl" % _HP)) > 6 else None
    if tbl_edu is not None:
        coords = [(0, 0, 3, 0, 4, 0), (0, 0, 3, 0, 4, 0)]  # fallback
        # row0: period col0, school col3, major col4 — 2 entries use row0 split cols
        edu_coords = [
            (0, 0, 3, 0, 4, 0),
            (5, 0, 3, 0, 4, 0),
        ]
        for i, (period, school, major) in enumerate(education[:2]):
            if i >= len(edu_coords):
                break
            pc, pr, sc, sr, mc, mr = edu_coords[i]
            if i == 1:
                # second line: use row below labels — col 1 and 3 on row 2 if present
                pc, pr, sc, sr, mc, mr = 1, 2, 3, 2, 4, 2
            for col, row, val in ((pc, pr, period), (sc, sr, school), (mc, mr, major)):
                tc = _tc_at(tbl_edu, col, row)
                if tc is not None and _set_tc_text(tc, val):
                    changed = True
            rep.tables_filled.append(f"학력{i+1}")

    tbl_lic = _find_tbl_by_snippet(root, "자격증/면허증")
    if tbl_lic is not None:
        for ri, (name, dt, grade, issuer) in enumerate(licenses[:2], start=1):
            for col, val in enumerate((name, dt, grade, issuer)):
                tc = _tc_at(tbl_lic, col, ri)
                if tc is not None and _set_tc_text(tc, val):
                    changed = True
            rep.tables_filled.append(f"자격{ri}")

    tbl_car = _find_tbl_by_snippet(root, "주요 근무처")
    if tbl_car is not None:
        for ri, (org, period, title, duty) in enumerate(careers[:4], start=1):
            for col, val in enumerate((org, period, title, duty)):
                tc = _tc_at(tbl_car, col, ri)
                if tc is not None and _set_tc_text(tc, val):
                    changed = True
            rep.tables_filled.append(f"경력{ri}")

    if sign_date or sign_name:
        for t in root.iter(_q("t")):
            txt = t.text or ""
            if "2026년" in txt and "월" in txt and "일" in txt and sign_date:
                t.text = sign_date
                changed = True
                rep.tables_filled.append("서명일")
                break
        if sign_name:
            for t in root.iter(_q("t")):
                if (t.text or "").strip() == "신청인":
                    # next sibling run often name — set following empty t
                    p = t.getparent()
                    if p is not None:
                        runs = list(p.iter(_q("t")))
                        idx = runs.index(t) if t in runs else -1
                        if idx >= 0 and idx + 1 < len(runs):
                            nxt = runs[idx + 1]
                            if not (nxt.text or "").strip():
                                nxt.text = sign_name
                                changed = True
                                rep.tables_filled.append("신청인")
                                break

    if changed:
        standalone = _detect_standalone(data[sec_name])
        data[sec_name] = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=standalone
        )

    tmp = dst.with_suffix(dst.suffix + ".part")
    with zipfile.ZipFile(tmp, "w") as zout:
        for name in names:
            zout.writestr(name, data[name])
    if in_place:
        os.replace(tmp, src)
    else:
        os.replace(tmp, dst)
    rep.ok = changed
    return rep
