# -*- coding: utf-8 -*-
"""F1 보조 — 서명 줄 위의 빈 날짜('2026년  월  일')에 사용자가 지정한 날짜를 기입한다(양식 공통).

날짜는 사용자가 명시한 값만 쓴다(오늘 날짜를 임의로 넣지 않는다 — hwpx_fill 의 날짜 날조 금지와 동일 원칙).
'연도'만 있고 월·일이 모두 빈 줄만 대상이며, 연도가 지정 날짜와 다르면 건드리지 않고 REVIEW 로 남긴다.
이미 월·일이 있는 줄은 덮어쓰지 않는다. 원본 파일은 읽기만 한다.

실양식의 날짜 줄은 `<t>2026년<tab/> 월<tab/> 일</t>` 처럼 탭 요소가 글자 사이에 끼어 있어
t.text 만으로는 '월'·'일'을 찾을 수 없다. t 의 직계 글자 조각(t.text + 자식 요소 tail)을 문서 순서로
이어 붙여 찾고, '월'·'일' 글자 바로 앞에 숫자만 끼워 넣는다(기존 공백·탭 모양 유지).
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from core.docx.services.hwpx_fill import _inline_texts, _invalidate_lineseg, _local

from .hwpx_xml import assert_not_same, parse_xml, read_hwpx, section_names, serialize_xml, write_hwpx
from .status import Finding, Status

_BLANK_DATE_RE = re.compile(r"(?<!\d)(\d{4})\s*년\s*월\s*일")
_MAX_PARAGRAPH_LEN = 60  # 날짜 줄은 짧다.
_MAX_OTHER_CHARS = 8     # 날짜 말고 다른 글자가 이보다 많으면 문장 속 '년 월 일'(예: 계약일 문구)로 보고 건드리지 않는다.


def _fragments(p) -> list[tuple[Any, str, str]]:
    """문단 직계 글자 조각 [(요소, 'text'|'tail', 글자)] — 요소 사이(탭 등)는 글자 1칸('\\t')으로 센다."""
    out: list[tuple[Any, str, str]] = []
    for t in _inline_texts(p):
        out.append((t, "text", t.text or ""))
        for child in t:
            out.append((child, "marker", "\t"))
            out.append((child, "tail", child.tail or ""))
    return out


def _fill_paragraph(p, when: _dt.date) -> str:
    """반환: 'filled' | 'none' | 'year_mismatch' | 'unsupported'."""
    frags = _fragments(p)
    flat = "".join(f[2] for f in frags)
    if len(flat) > _MAX_PARAGRAPH_LEN:
        return "none"
    m = _BLANK_DATE_RE.search(flat)
    if m is None:
        return "none"
    if len((flat[:m.start()] + flat[m.end():]).strip()) > _MAX_OTHER_CHARS:
        return "none"
    if int(m.group(1)) != when.year:
        return "year_mismatch"
    month_at = flat.index("월", m.start(1))
    day_at = flat.index("일", month_at)
    inserts = {month_at: str(when.month), day_at: str(when.day)}
    # flat 위치 → (조각 인덱스, 조각 안 오프셋)
    pos = 0
    plan: list[tuple[int, int, str]] = []
    for idx, (_el, kind, text) in enumerate(frags):
        for at, digits in inserts.items():
            if pos <= at < pos + len(text) and kind in ("text", "tail"):
                plan.append((idx, at - pos, digits))
        pos += len(text)
    if len(plan) != 2:
        return "unsupported"
    for idx, off, digits in sorted(plan, key=lambda x: (x[0], -x[1])):  # 뒤쪽 오프셋부터 끼워 넣어 앞 오프셋 보존
        el, kind, text = frags[idx]
        new = text[:off] + digits + text[off:]
        if kind == "text":
            el.text = new
        else:
            el.tail = new
        frags[idx] = (el, kind, new)
    _invalidate_lineseg(p)
    return "filled"


def fill_date_lines(in_hwpx, out_hwpx, when: _dt.date) -> dict[str, Any]:
    """빈 날짜 줄에 when 의 월·일을 채워 out_hwpx 로 저장한다(원본 미수정)."""
    assert_not_same(in_hwpx, out_hwpx)
    infos, data = read_hwpx(in_hwpx)
    findings: list[Finding] = []
    filled = 0
    for name in section_names(data):
        root = parse_xml(data[name])
        changed = False
        for p in root.iter():
            if _local(getattr(p, "tag", "")) != "p":
                continue
            state = _fill_paragraph(p, when)
            if state == "filled":
                filled += 1
                changed = True
            elif state == "year_mismatch":
                findings.append(Finding(
                    "DATE_YEAR_MISMATCH", Status.REVIEW,
                    f"날짜 줄의 연도가 지정 날짜({when.year}년)와 달라 기입하지 않음 — 사용자 확인 필요",
                    source="engine", evidence=name))
            elif state == "unsupported":
                findings.append(Finding(
                    "DATE_CROSS_RUN", Status.REVIEW,
                    "날짜 줄 모양이 달라 기입하지 않음 — 사용자 확인 필요", source="engine", evidence=name))
        if changed:
            data[name] = serialize_xml(root, data[name])
    write_hwpx(infos, data, out_hwpx)
    if filled:
        findings.insert(0, Finding(
            "DATE_FILLED", Status.PASS,
            f"자동 검사 PASS: 서명 줄 빈 날짜 {filled}곳에 지정 날짜({when.year}-{when.month:02d}-{when.day:02d}) 기입",
            source="engine", meta={"filled": filled, "date": when.isoformat()}))
    return {"output": str(out_hwpx), "filled": filled, "findings": findings}
