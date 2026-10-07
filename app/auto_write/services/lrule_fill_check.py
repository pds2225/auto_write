# -*- coding: utf-8 -*-
"""lrule_fill_check — L규칙 3단계 판정의 2단계(채움 여부) 검사기.

"파일이 안 깨졌는가"가 아니라 "칸이 실제로 채워졌는가"를 읽기 전용으로 본다.
HWPX(section*.xml)와 DOCX(word/document.xml)의 표를 같은 모양으로 바꿔 분석한다.

찾는 결함(모두 위치 정보 포함)
- ``blank``           : 라벨 오른쪽 또는 머리행 아래의 값칸이 비었거나 공백뿐이다.
- ``instruction``     : 값칸에 "~시에만 기재" 같은 안내문만 남아 있다.
- ``repeat_partial``  : 반복 칸(표 2행 이후)이 첫 회만 채워지고 나머지가 비었다.
- ``unchecked``       : □ 선택칸에 ■ 가 하나도 없다(선택 안 함).

어떤 L규칙이 어떤 결함을 "미채움"으로 보는지는 ``FILL_RULES`` 가 정한다.
L009·L010 처럼 공란을 허용하는 규칙은 일부러 넣지 않았다.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

__all__ = ["FillFinding", "FillReport", "FILL_RULES", "inspect_fill", "is_fill_rule"]

# 규칙 코드 → 그 규칙이 '미채움'으로 취급하는 결함 종류.
FILL_RULES: dict[str, frozenset[str]] = {
    "L012": frozenset({"instruction"}),  # 안내문구는 값칸을 채운 뒤 남으면 안 된다
    "L053": frozenset({"blank", "instruction", "repeat_partial"}),  # 고정 양식 채움(없으면 '해당사항 없음')
    "L070": frozenset({"blank", "instruction", "repeat_partial"}),  # 값칸 채움
    "L025": frozenset({"unchecked"}),  # □→■ 체크
    "L034": frozenset({"unchecked"}),
    "L052": frozenset({"unchecked"}),
    "L086": frozenset({"unchecked"}),
}

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_EMPTY_CHARS = " \t\r\n 　​﻿"
_LABEL_MAX = 40
_INSTRUCTION_MAX = 80
_INSTRUCTION_RES = (
    re.compile(r"(시|경우|때)\s*(에만|만)?\s*(기재|작성|입력|기입)"),
    re.compile(r"(기재|작성|입력|기입)\s*(하여|하세요|하십시오|하시오|바랍니다|요망|해\s*주)"),
)
_LOCATION_LIMIT = 5


def _is_blank(text: str) -> bool:
    return not text.strip(_EMPTY_CHARS)


def _is_instruction(text: str) -> bool:
    compact = text.strip(_EMPTY_CHARS)
    if not compact or len(compact) > _INSTRUCTION_MAX:
        return False
    return any(p.search(compact) for p in _INSTRUCTION_RES)


@dataclass
class _Cell:
    row: int
    col: int
    text: str = ""
    has_object: bool = False  # 그림·체크버튼·중첩표 등 글자 없이도 채워진 것으로 보는 내용

    @property
    def filled(self) -> bool:
        return self.has_object or not _is_blank(self.text)


@dataclass
class FillFinding:
    """미채움 결함 1건."""

    kind: str
    location: str
    label: str = ""
    text: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "location": self.location, "label": self.label, "text": self.text}


@dataclass
class FillReport:
    """산출물 1개의 채움 검사 결과."""

    supported: bool = True
    error: str = ""
    suffix: str = ""
    tables: int = 0
    cells: int = 0
    findings: list[FillFinding] = field(default_factory=list)

    def for_rule(self, code: str) -> list[FillFinding]:
        kinds = FILL_RULES.get(code, frozenset())
        return [f for f in self.findings if f.kind in kinds]

    def as_dict(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for f in self.findings:
            by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        return {
            "supported": self.supported,
            "error": self.error,
            "suffix": self.suffix,
            "tables": self.tables,
            "cells": self.cells,
            "findings_by_kind": by_kind,
            "findings": [f.as_dict() for f in self.findings],
        }


def is_fill_rule(code: str) -> bool:
    return code in FILL_RULES


def format_locations(findings: list[FillFinding], limit: int = _LOCATION_LIMIT) -> str:
    """증거 문자열: 앞 ``limit`` 건의 위치 + 나머지 개수."""
    head = "; ".join(f"[{f.kind}] {f.location}" for f in findings[:limit])
    extra = len(findings) - limit
    return head + (f" 외 {extra}건" if extra > 0 else "")


def _ln(el: Any) -> str:
    tag = getattr(el, "tag", "")
    return etree.QName(el).localname if isinstance(tag, str) and "}" in tag else (tag if isinstance(tag, str) else "")


def _cell_label(cell: _Cell) -> str:
    return cell.text.strip(_EMPTY_CHARS)[:20]


# ── 표 → 행렬 어댑터 ────────────────────────────────────────────────────────────

def _hwpx_tables(root: Any) -> list[list[list[_Cell]]]:
    """section XML 안의 모든 hp:tbl(중첩 포함)을 행×칸 구조로 바꾼다."""
    ns = {"hp": _HP}
    tables: list[list[list[_Cell]]] = []
    for tbl in root.iter(f"{{{_HP}}}tbl"):
        rows: list[list[_Cell]] = []
        for r_idx, tr in enumerate(tbl.findall("hp:tr", ns)):
            row: list[_Cell] = []
            for c_idx, tc in enumerate(tr.findall("hp:tc", ns)):
                addr = tc.find("hp:cellAddr", ns)
                col = int(addr.get("colAddr", c_idx)) if addr is not None else c_idx
                rw = int(addr.get("rowAddr", r_idx)) if addr is not None else r_idx
                text = "".join("".join(t.itertext()) for t in tc.iter(f"{{{_HP}}}t"))
                has_obj = any(
                    _ln(el) in {"pic", "checkBtn", "tbl", "ole", "container", "equation"}
                    for el in tc.iter() if el is not tc
                )
                row.append(_Cell(rw, col, text, has_obj))
            if row:
                rows.append(row)
        if rows:
            tables.append(rows)
    return tables


def _docx_tables(root: Any) -> list[list[list[_Cell]]]:
    tables: list[list[list[_Cell]]] = []
    for tbl in root.iter(f"{{{_W}}}tbl"):
        rows: list[list[_Cell]] = []
        for r_idx, tr in enumerate(tbl.findall(f"{{{_W}}}tr")):
            row: list[_Cell] = []
            col = 0
            for tc in tr.findall(f"{{{_W}}}tc"):
                span = tc.find(f"{{{_W}}}tcPr/{{{_W}}}gridSpan")
                width = int(span.get(f"{{{_W}}}val", 1)) if span is not None else 1
                text = "".join(t.text or "" for t in tc.iter(f"{{{_W}}}t"))
                has_obj = any(
                    _ln(el) in {"drawing", "pict", "tbl", "object", "sdt"}
                    for el in tc.iter() if el is not tc
                )
                row.append(_Cell(r_idx, col, text, has_obj))
                col += width
            if row:
                rows.append(row)
        if rows:
            tables.append(rows)
    return tables


# ── 분석 ───────────────────────────────────────────────────────────────────────

def _analyze_table(table: list[list[_Cell]], t_no: int, tag: str, out: list[FillFinding]) -> None:
    header_idx = next(
        (i for i, row in enumerate(table) if len(row) >= 2 and all(c.filled and not c.has_object and c.text.strip(_EMPTY_CHARS) for c in row)),
        None,
    )
    seen: set[tuple[int, int]] = set()
    for r_pos, row in enumerate(table):
        ordered = sorted(row, key=lambda c: c.col)
        for i, cell in enumerate(ordered):
            where = f"{tag}표{t_no} {r_pos + 1}행 {cell.col + 1}열"
            left = ordered[i - 1] if i > 0 else None
            left_label = left is not None and left.filled and not left.has_object and len(left.text.strip(_EMPTY_CHARS)) <= _LABEL_MAX
            below_header = header_idx is not None and r_pos > header_idx
            value_position = bool(left_label) or below_header
            key = (r_pos, cell.col)
            if not cell.filled and value_position and key not in seen:
                seen.add(key)
                earlier = any(
                    c.filled and c.col == cell.col
                    for prev in table[(header_idx + 1 if header_idx is not None else 0):r_pos] for c in prev
                )
                label = _cell_label(left) if left_label and left is not None else (
                    _cell_label(next((c for c in table[header_idx] if c.col == cell.col), cell)) if header_idx is not None else ""
                )
                kind = "repeat_partial" if earlier else "blank"
                out.append(FillFinding(kind, where, label))
            elif cell.filled and value_position and not cell.has_object and _is_instruction(cell.text):
                out.append(FillFinding("instruction", where, _cell_label(left) if left_label and left is not None else "",
                                       cell.text.strip(_EMPTY_CHARS)[:40]))
            if cell.text.count("□") and "■" not in cell.text:
                out.append(FillFinding("unchecked", where, _cell_label(left) if left_label and left is not None else "",
                                       cell.text.strip(_EMPTY_CHARS)[:40]))


def inspect_fill(path: str | Path) -> FillReport:
    """산출물 채움 검사. 지원하지 않는 형식은 ``supported=False``, 읽기 실패는 ``error`` 기록."""
    artifact = Path(path)
    suffix = artifact.suffix.lower()
    report = FillReport(suffix=suffix)
    if suffix not in {".hwpx", ".docx"}:
        report.supported = False
        report.error = f"채움 검사 미지원 형식: {suffix or 'unknown'}"
        return report
    try:
        tables: list[tuple[str, list[list[_Cell]]]] = []
        with zipfile.ZipFile(artifact) as z:
            if suffix == ".hwpx":
                for name in sorted(n for n in z.namelist() if _SECTION_RE.search(n)):
                    stem = Path(name).stem
                    tables += [(f"{stem} ", t) for t in _hwpx_tables(etree.fromstring(z.read(name)))]
            else:
                tables += [("", t) for t in _docx_tables(etree.fromstring(z.read("word/document.xml")))]
        report.tables = len(tables)
        for n, (tag, table) in enumerate(tables, 1):
            report.cells += sum(len(r) for r in table)
            _analyze_table(table, n, tag, report.findings)
    except Exception as exc:  # 읽기 실패는 통과로 보지 않고 호출자가 UNVERIFIABLE 처리
        report.error = f"{type(exc).__name__}: {exc}"
    return report
