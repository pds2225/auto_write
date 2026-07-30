"""hwpx_fill_coverage — HWPX 신청서 섹션별 채움률 리포트."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

from .hwpx_fill import _HP, _cell_text, _direct, _direct_form_checkbtns, _q
from .hwpx_resume_supplement import _is_fillable_cell_text


@dataclass
class SectionCoverage:
    name: str
    filled: int = 0
    empty: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.filled + self.empty

    @property
    def rate(self) -> float:
        return (self.filled / self.total) if self.total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "filled": self.filled,
            "empty": self.empty,
            "total": self.total,
            "rate": round(self.rate, 3),
            "notes": self.notes,
        }


@dataclass
class CoverageReport:
    path: str
    sections: list[SectionCoverage] = field(default_factory=list)
    ok: bool = True
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ok": self.ok,
            "sections": [s.as_dict() for s in self.sections],
            "overall_rate": round(
                (
                    sum(s.filled for s in self.sections)
                    / max(1, sum(s.total for s in self.sections))
                ),
                3,
            ),
            "notes": self.notes,
        }


def _section_xml_blob(path: Path) -> etree._Element:
    with zipfile.ZipFile(path) as z:
        name = "Contents/section0.xml"
        if name not in z.namelist():
            secs = [n for n in z.namelist() if "section" in n and n.endswith(".xml")]
            name = sorted(secs)[0]
        return etree.fromstring(z.read(name))


def _find_tbl(root, *snippets: str):
    for tbl in root.iter(_q("tbl")):
        blob = "".join(tbl.itertext())
        if any(s in blob for s in snippets):
            return tbl
    return None


def _count_value_cells(tbl, *, skip_header: bool = True) -> tuple[int, int]:
    filled = empty = 0
    for tr in _direct(tbl, "tr"):
        cells = _direct(tr, "tc")
        texts = [_cell_text(c).strip() for c in cells]
        if skip_header and texts and all(
            t in {"주요 근무처", "근무기간", "직  위", "담당업무", "자격증/면허증", "취득일", "등  급", "발행처",
                  "공적(포상)명", "수상일", "발행처", "성명(국문)", "소속/직위", "휴대전화", "생년월일", "이 메 일", "주소(거주지)"}
            or not t
            for t in texts
        ):
            # crude: if first row looks like headers only
            if any(t in {"주요 근무처", "자격증/면허증", "공적(포상)명", "성명(국문)"} for t in texts):
                continue
        for tc, t in zip(cells, texts):
            if _direct_form_checkbtns(tc):
                continue
            # 라벨만 있는 짧은 헤더 셀 스킵
            if t in {"주요 근무처", "근무기간", "직  위", "담당업무", "자격증/면허증", "취득일", "등  급", "발행처",
                     "공적(포상)명", "수상일", "성명(국문)", "소속/직위", "휴대전화", "생년월일", "이 메 일", "주소(거주지)",
                     "모집분야"}:
                continue
            if _is_fillable_cell_text(t) or not t:
                empty += 1
            else:
                filled += 1
    return filled, empty


def score_hwpx_coverage(path: str | Path) -> CoverageReport:
    """신청서 HWPX 섹션별 채움률."""
    p = Path(path)
    rep = CoverageReport(path=str(p))
    if not p.is_file():
        rep.ok = False
        rep.notes.append("파일 없음")
        return rep
    root = _section_xml_blob(p)

    # 인적
    sec = SectionCoverage("인적")
    tbl = _find_tbl(root, "성명(국문)", "소속/직위")
    if tbl is not None:
        # 값 칸만: 짝수 인덱스가 라벨인 4행 표
        for tr in _direct(tbl, "tr"):
            cells = _direct(tr, "tc")
            for i, tc in enumerate(cells):
                if i % 2 == 0:
                    continue
                t = _cell_text(tc).strip()
                if _is_fillable_cell_text(t) or not t:
                    sec.empty += 1
                else:
                    sec.filled += 1
    else:
        sec.notes.append("표 없음")
    rep.sections.append(sec)

    # 학력
    sec = SectionCoverage("학력")
    tbl = _find_tbl(root, "졸업/수료", "학력사항")
    if tbl is not None:
        f, e = _count_value_cells(tbl)
        sec.filled, sec.empty = f, e
    rep.sections.append(sec)

    # 자격
    sec = SectionCoverage("자격")
    tbl = _find_tbl(root, "자격증/면허증")
    if tbl is not None:
        f, e = _count_value_cells(tbl)
        sec.filled, sec.empty = f, e
    rep.sections.append(sec)

    # 경력
    sec = SectionCoverage("경력")
    tbl = _find_tbl(root, "주요 근무처")
    if tbl is not None:
        f, e = _count_value_cells(tbl)
        sec.filled, sec.empty = f, e
    rep.sections.append(sec)

    # 모집분야 (체크)
    sec = SectionCoverage("모집분야")
    tbl = _find_tbl(root, "참여 신청서", "전문분야 선택")
    checked = 0
    total_btn = 0
    if tbl is not None:
        for tr in _direct(tbl, "tr"):
            for tc in _direct(tr, "tc"):
                btns = _direct_form_checkbtns(tc)
                for b in btns:
                    total_btn += 1
                    if b.get("value") == "CHECKED":
                        checked += 1
        sec.filled = checked
        sec.empty = max(0, 3 - checked)  # 3옵션 기준 미체크를 empty로
        if checked == 0:
            sec.notes.append("미체크(confirm 필요·L034)")
    rep.sections.append(sec)

    # 서명일
    sec = SectionCoverage("서명")
    blob = "".join(root.itertext())
    if re.search(r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일", blob):
        sec.filled = 1
    elif re.search(r"\d{4}\s*년\s*월\s*일", blob):
        sec.empty = 1
        sec.notes.append("날짜 미기입")
    else:
        sec.empty = 1
    rep.sections.append(sec)

    return rep
