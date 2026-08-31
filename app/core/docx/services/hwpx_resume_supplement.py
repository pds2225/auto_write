"""hwpx_resume_supplement — 이력서 사실값으로 HWPX 표·서명 칸 보강(RHWP).

cross_form/hwpx_fill 이 못 채우는 **좌표형 표**(학력·자격·경력)와 서명일을
호출자가 넘긴 facts 만으로 기입한다(날조 0). 모집분야 자동 체크는 기본 off
(L034 — confirm 후에만 check_columns 전달).
"""

from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from .hwpx_fill import (
    _HP,
    _cell_text,
    _direct,
    _direct_form_checkbtns,
    _has_form_control,
    _invalidate_lineseg,
    _q,
    _same_file,
    _set_cell_text,
)

_STANDALONE_RE = re.compile(rb"standalone\s*=\s*['\"](yes|no)['\"]")

# 학력/자격/경력 칸에 흔히 있는 '보이는 빈칸' 플레이스홀더
_PLACEHOLDER_TEXTS = {
    "~",
    "(yyyy/mm/dd)",
    "( )",
    " ",
    "",
}
_PLACEHOLDER_RE = re.compile(
    r"^(년\s*월|졸업/수료|대학교|전공|\(yyyy|/mm/dd\)|\(\s*\)|~)+$",
    re.IGNORECASE,
)


def canonical_sign_date(*, today: date | None = None) -> str:
    """서명일·작성일은 실행 시점 날짜만 쓴다(L032).

    대화·RESUME·facts JSON 의 낡은 날짜는 호출자가 넘기더라도 이 값을 써야 한다.
    형식은 한글 양식 ``YYYY년  M월  D일`` (앞에 0 없음, 년/월 뒤 공백 2).
    """
    d = today or date.today()
    return f"{d.year}년  {d.month}월  {d.day}일"


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


def _is_fillable_cell_text(cur: str) -> bool:
    s = (cur or "").strip()
    if s in _PLACEHOLDER_TEXTS:
        return True
    if s.startswith("(yyyy"):
        return True
    # "년    월  (졸업/수료)" / "대학교     전공"
    compact = re.sub(r"\s+", "", s)
    if "년" in compact and "월" in compact and ("졸업" in compact or "수료" in compact):
        return True
    if compact.startswith("대학교") and "전공" in compact:
        return True
    if _PLACEHOLDER_RE.match(compact):
        return True
    return False


def _set_tc_text(tc, text: str, *, force_placeholder: bool = False) -> bool:
    """값 칸 텍스트 설정. 빈칸·플레이스홀더만(실값 보호).

    기입은 ``_set_cell_text`` 로 위임한다 — 폼컨트롤 칸 거부(L086)와
    줄위치 캐시 제거(L002/L145)가 빠지지 않는다.
    """
    cur = _cell_text(tc).strip()
    if cur and not _is_fillable_cell_text(cur) and not force_placeholder:
        return False
    if _has_form_control(tc):
        return False
    return _set_cell_text(tc, text)


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


def _empty_data_rows(tbl, header_row: int = 0) -> list[int]:
    """헤더 다음부터 채울 수 있는 rowAddr 목록."""
    rows: set[int] = set()
    for tr in _direct(tbl, "tr"):
        for tc in _direct(tr, "tc"):
            addr = tc.find(_q("cellAddr"))
            if addr is None:
                continue
            ra = int(addr.get("rowAddr", -1))
            if ra > header_row:
                rows.add(ra)
    return sorted(rows)


def load_resume_facts(path: str | Path) -> dict[str, Any]:
    """facts JSON: education/licenses/careers/sign_* / check_columns(optional)."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return data


def facts_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    """정규화: list[list] → tuple lists."""
    edu = [tuple(x) for x in data.get("education") or []]
    lic = [tuple(x) for x in data.get("licenses") or []]
    car = [tuple(x) for x in data.get("careers") or []]
    checks = [tuple(x) for x in data.get("check_columns") or []]
    return {
        "education": edu,
        "licenses": lic,
        "careers": car,
        "specialty_text": str(data.get("specialty_text") or ""),
        "check_columns": checks,
        "sign_date": str(data.get("sign_date") or ""),
        "sign_name": str(data.get("sign_name") or ""),
    }


def supplement_hwpx_from_resume(
    in_hwpx: str | Path,
    out_hwpx: str | Path,
    *,
    education: Optional[list[tuple[str, ...]]] = None,
    licenses: Optional[list[tuple[str, ...]]] = None,
    careers: Optional[list[tuple[str, ...]]] = None,
    specialty_text: str = "",
    check_columns: Optional[list[tuple[int, int, str]]] = None,
    sign_date: str = "",
    sign_name: str = "",
    facts_json: Optional[str | Path] = None,
    today: date | None = None,
    sample_ok: bool = True,
    full_document: bool = False,
) -> ResumeSupplementReport:
    """이력서 표 사실을 HWPX 신청서 표에 좌표 기입."""
    from .submission_gates import require_sample_ok

    require_sample_ok(sample_ok=sample_ok, full_document=full_document)
    if facts_json is not None:
        f = facts_from_dict(load_resume_facts(facts_json))
        education = education if education is not None else f["education"]
        licenses = licenses if licenses is not None else f["licenses"]
        careers = careers if careers is not None else f["careers"]
        specialty_text = specialty_text or f["specialty_text"]
        check_columns = check_columns if check_columns is not None else f["check_columns"]
        sign_date = sign_date or f["sign_date"]
        sign_name = sign_name or f["sign_name"]

    education = list(education or [])
    licenses = list(licenses or [])
    careers = list(careers or [])
    check_columns = list(check_columns or [])
    if sign_date:
        sign_date = canonical_sign_date(today=today)

    src, dst = Path(in_hwpx), Path(out_hwpx)
    rep = ResumeSupplementReport(input=str(src), output=str(dst))
    if not src.is_file():
        rep.notes.append("입력 없음")
        return rep
    in_place = _same_file(src, dst)
    if in_place:
        dst = src.with_suffix(src.suffix + ".sup.part")
        rep.output = str(out_hwpx)

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

    # 모집분야: confirm 으로 check_columns 가 온 경우만
    tbl_app = _find_tbl_by_snippet(root, "전문상담위원 참여 신청서")
    if tbl_app is None:
        tbl_app = _find_tbl_by_snippet(root, "참여 신청서")
    if tbl_app is not None:
        for col, row, label in check_columns:
            if _check_btn(tbl_app, int(col), int(row)):
                rep.checks_set.append(str(label))
                changed = True
        if specialty_text:
            tc = _tc_at(tbl_app, 3, 7)
            if tc is not None and _set_tc_text(tc, specialty_text):
                rep.tables_filled.append("모집분야_세부")
                changed = True

    # 학력: row1/row2 의 플레이스홀더 치환 (양식: 년월 | 대학교 전공)
    tbl_edu = _find_tbl_by_snippet(root, "학력사항")
    if tbl_edu is None:
        tbl_edu = _find_tbl_by_snippet(root, "졸업/수료")
    if tbl_edu is None:
        tbl_edu = _find_tbl_by_snippet(root, "대학교")
    if tbl_edu is not None and education:
        edu_rows = [1, 2]
        for i, entry in enumerate(education[:2]):
            period, school, major = (list(entry) + ["", "", ""])[:3]
            ra = edu_rows[i]
            period_done = False
            for col in (0, 1):
                tc = _tc_at(tbl_edu, col, ra)
                if tc is not None and _is_fillable_cell_text(_cell_text(tc)):
                    if _set_tc_text(tc, period):
                        period_done = True
                        changed = True
                        break
            school_major = f"{school} {major}".strip()
            school_done = False
            for col in (2, 3, 4, 5):
                tc = _tc_at(tbl_edu, col, ra)
                if tc is not None and _is_fillable_cell_text(_cell_text(tc)):
                    if _set_tc_text(tc, school_major):
                        school_done = True
                        changed = True
                        break
            if period_done or school_done:
                rep.tables_filled.append(f"학력{i+1}")
            else:
                rep.notes.append(f"학력{i+1} 칸을 찾지 못함")

    tbl_lic = _find_tbl_by_snippet(root, "자격증/면허증")
    if tbl_lic is not None and licenses:
        for ri, entry in enumerate(licenses[:2], start=1):
            name, dt, grade, issuer = (list(entry) + ["", "", "", ""])[:4]
            for col, val in enumerate((name, dt, grade, issuer)):
                tc = _tc_at(tbl_lic, col, ri)
                if tc is not None and _set_tc_text(tc, val):
                    changed = True
            rep.tables_filled.append(f"자격{ri}")

    tbl_car = _find_tbl_by_snippet(root, "주요 근무처")
    if tbl_car is not None and careers:
        data_rows = _empty_data_rows(tbl_car, header_row=0)
        # 마지막 빈 서명행 제외 가능 — 채울 행 수 = min(career, data_rows)
        for i, entry in enumerate(careers):
            if i >= len(data_rows):
                break
            ri = data_rows[i]
            org, period, title, duty = (list(entry) + ["", "", "", ""])[:4]
            for col, val in enumerate((org, period, title, duty)):
                tc = _tc_at(tbl_car, col, ri)
                if tc is not None and _set_tc_text(tc, val):
                    changed = True
            rep.tables_filled.append(f"경력{i+1}")

    if sign_date:
        for t in root.iter(_q("t")):
            txt = t.text or ""
            if re.search(r"\d{4}\s*년", txt) and "월" in txt and "일" in txt:
                t.text = sign_date
                _invalidate_lineseg(t)
                changed = True
                rep.tables_filled.append("서명일")
                break
    if sign_name:
        for t in root.iter(_q("t")):
            if (t.text or "").strip() == "신청인":
                p = t.getparent()
                if p is not None:
                    runs = list(p.iter(_q("t")))
                    try:
                        idx = runs.index(t)
                    except ValueError:
                        idx = -1
                    if idx >= 0 and idx + 1 < len(runs):
                        nxt = runs[idx + 1]
                        if not (nxt.text or "").strip():
                            nxt.text = sign_name
                            _invalidate_lineseg(nxt)
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
        if "mimetype" in data:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, data["mimetype"])
        for name in names:
            if name == "mimetype":
                continue
            zout.writestr(name, data[name])
    if in_place:
        os.replace(tmp, src)
    else:
        os.replace(tmp, dst)
    rep.ok = changed
    return rep
