# -*- coding: utf-8 -*-
"""hwpx_layout_fix — 채워진 HWPX 레이아웃 정규화(전체 양식 공통·멱등·원본 보존).

2026-07-11 사용자 지시(프로필/이력서 표 실측)로 도출한 3종 결정론 후처리.
본문 내용은 만들지 않는다(날조 0). 값·라벨 텍스트는 손대지 않는다(무손실).

1. clamp_letter_spacing(header)      — charPr 자간(hh:spacing hangul/latin/…) '하한' clamp.
   과압축(예: -50%)만 하한값(기본 -30%)으로 완화. 정상/완만한 자간(-30~+)은 보존.
   → "글씨 자간이 너무 좁은 것" 재발 방지 가드.
2. relax_forced_single_line(section) — 줄위치 캐시(hp:linesegarray) 제거.
   한글이 문서를 열 때 셀 폭에 맞춰 줄을 다시 계산 → 한 줄 강제로 잘리던 긴 텍스트가
   여러 줄로 자동 줄바꿈("1줄에 다 넣을 필요 없음, 여러 줄로 작성").
   (엔진 hwpx_fill._strip_linesegarray 와 동일 메커니즘 — 여기서는 후처리 진입점으로 노출.)
3. merge_trailing_empty_value_cells(section) — '라벨-값' 표에서 오른쪽 '전부 빈' 열들을
   값 셀에 수평 병합(colSpan 확장). **보수 규칙**(사용자 확정): 표의 오른쪽 연속 열이
   '모든 행에서' 전부 비어 있고, 남는 열이 2개 이상(라벨+값)이며, 0열이 과반 행에서
   라벨(비어있지 않음)일 때만 병합. 어느 행이든 그 열에 값이 있는 '진짜 다열 표'
   (예: 경력표 기간|직장명|부서|담당업무)는 절대 건드리지 않는다.

안전 불변: 원본 미수정(out==in 이면 ValueError)·멱등·병합은 span 1x1 단순표만.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

__all__ = [
    "clamp_letter_spacing",
    "strip_linesegarray",
    "relax_forced_single_line",
    "merge_trailing_empty_value_cells",
    "finalize_layout_hwpx",
    "DEFAULT_SPACING_FLOOR",
]

_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_HEADER_RE = re.compile(r"header\.xml$", re.IGNORECASE)

# 자간 언어별 속성(HWPML charPr/spacing). percent 단위(HWP UI -50~50%).
_SPACING_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")
DEFAULT_SPACING_FLOOR = -30


def _ln(el) -> str:
    t = getattr(el, "tag", "")
    return etree.QName(el).localname if isinstance(t, str) and "}" in t else (t or "")


def _child(el, name):
    for c in el:
        if _ln(c) == name:
            return c
    return None


# --- 1) 자간 하한 clamp -------------------------------------------------------
def clamp_letter_spacing(header_root, floor: int = DEFAULT_SPACING_FLOOR) -> int:
    """header.xml charPr 자간(spacing)이 floor 보다 좁으면(더 음수) floor 로 완화.

    charPr 직속 spacing 만 대상(section 의 lineseg 'spacing'=줄높이 는 건드리지 않음).
    반환: 완화한 (element,lang) 개수.
    """
    n = 0
    for sp in header_root.iter():
        if _ln(sp) != "spacing":
            continue
        parent = sp.getparent()
        if parent is None or _ln(parent) != "charPr":
            continue
        for lang in _SPACING_LANGS:
            v = sp.get(lang)
            if v is None:
                continue
            try:
                iv = int(v)
            except (TypeError, ValueError):
                continue
            if iv < floor:
                sp.set(lang, str(floor))
                n += 1
    return n


# --- 2) 한 줄 강제 해제(여러 줄 재계산) ---------------------------------------
def strip_linesegarray(section_root) -> int:
    """줄위치 캐시(hp:linesegarray) 전부 제거 → 한글이 열 때 줄위치·줄바꿈 재계산."""
    n = 0
    for ls in list(section_root.iter()):
        if _ln(ls) == "linesegarray":
            par = ls.getparent()
            if par is not None:
                par.remove(ls)
                n += 1
    return n


# 사용자 표현("여러 줄로 작성") 기준 별칭
relax_forced_single_line = strip_linesegarray


# --- 3) 라벨-값 표 오른쪽 빈 열 병합 ------------------------------------------
def _tc_is_empty(tc) -> bool:
    """셀에 실제 텍스트가 없고, 중첩 표/그림도 없으면 빈 셀."""
    for t in tc.iter():
        ln = _ln(t)
        if ln == "t" and (t.text or "").strip():
            return False
        if ln in ("tbl", "pic", "picture", "container", "ole"):
            return False
    return True


def _tc_col(tc) -> int:
    a = _child(tc, "cellAddr")
    if a is None:
        return -1
    try:
        return int(a.get("colAddr", "-1"))
    except (TypeError, ValueError):
        return -1


def _tc_span(tc, key) -> int:
    s = _child(tc, "cellSpan")
    if s is None:
        return 1
    try:
        return int(s.get(key, "1"))
    except (TypeError, ValueError):
        return 1


def _tc_width(tc) -> int:
    z = _child(tc, "cellSz")
    if z is None or z.get("width") is None:
        return 0
    try:
        return int(z.get("width"))
    except (TypeError, ValueError):
        return 0


def merge_trailing_empty_value_cells(section_root) -> int:
    """'라벨-값' 표의 오른쪽 '전부 빈' 열들을 값 셀에 수평 병합. 반환: 병합한 행 수."""
    merged_rows = 0
    for tbl in list(section_root.iter()):
        if _ln(tbl) != "tbl":
            continue
        try:
            col_cnt = int(tbl.get("colCnt") or "0")
        except (TypeError, ValueError):
            continue
        if col_cnt < 3:  # 라벨+값+빈1 최소
            continue
        rows = [tr for tr in tbl if _ln(tr) == "tr"]
        if len(rows) < 2:
            continue
        cells = [tc for tr in rows for tc in tr if _ln(tc) == "tc"]
        if not cells:
            continue
        # 단순표만(이미 병합된 셀이 있으면 위험 → 건너뜀)
        if any(_tc_span(tc, "colSpan") != 1 or _tc_span(tc, "rowSpan") != 1 for tc in cells):
            continue

        # 행별 colAddr→tc 매핑
        row_maps = []
        for tr in rows:
            m = {}
            for tc in tr:
                if _ln(tc) == "tc":
                    m[_tc_col(tc)] = tc
            row_maps.append(m)

        def col_all_empty(c: int) -> bool:
            present = False
            for m in row_maps:
                tc = m.get(c)
                if tc is None:
                    continue
                present = True
                if not _tc_is_empty(tc):
                    return False
            return present

        # 오른쪽 끝부터 '전부 빈' 열 블록 찾기
        k = col_cnt
        while k - 1 >= 0 and col_all_empty(k - 1):
            k -= 1
        if k >= col_cnt:      # 뒤쪽 빈 열 없음
            continue
        if k < 2:             # 라벨+값 최소 2열 안 남음(1열 표 등)
            continue

        # 0열이 과반 행에서 라벨(비어있지 않음)인가
        label_rows = sum(
            1 for m in row_maps if (m.get(0) is not None and not _tc_is_empty(m[0]))
        )
        if label_rows < max(1, len(rows) // 2 + len(rows) % 2):
            continue

        new_colspan = (col_cnt - 1) - (k - 1) + 1  # 값셀이 덮을 열 수
        for m in row_maps:
            value_tc = m.get(k - 1)
            if value_tc is None:
                continue
            total_w = _tc_width(value_tc)
            removed = 0
            for c in range(k, col_cnt):
                tc = m.get(c)
                if tc is None:
                    continue
                total_w += _tc_width(tc)
                par = tc.getparent()
                if par is not None:
                    par.remove(tc)
                    removed += 1
            if removed == 0:
                continue
            span = _child(value_tc, "cellSpan")
            if span is None:
                span = etree.Element(_qname_like(value_tc, "cellSpan"))
                span.set("rowSpan", "1")
                addr = _child(value_tc, "cellAddr")
                idx = list(value_tc).index(addr) + 1 if addr is not None else 0
                value_tc.insert(idx, span)
            span.set("colSpan", str(new_colspan))
            sz = _child(value_tc, "cellSz")
            if sz is not None and total_w > 0:
                sz.set("width", str(total_w))
            merged_rows += 1
    return merged_rows


def _qname_like(sibling, localname: str) -> str:
    """형제 요소와 같은 네임스페이스로 localname QName 생성."""
    qn = etree.QName(sibling)
    return f"{{{qn.namespace}}}{localname}" if qn.namespace else localname


# --- 파일 진입점 -------------------------------------------------------------
def finalize_layout_hwpx(
    in_path,
    out_path,
    *,
    spacing_floor: int | None = DEFAULT_SPACING_FLOOR,
    relax_lines: bool = True,
    merge_empty: bool = True,
) -> dict:
    """채워진 HWPX 에 레이아웃 정규화 3종을 적용해 out_path 로 저장. 원본 보존."""
    in_path, out_path = Path(in_path), Path(out_path)
    if in_path.resolve() == out_path.resolve():
        raise ValueError("원본 덮어쓰기 금지: 출력 경로가 입력과 같습니다.")

    with zipfile.ZipFile(in_path) as zin:
        infos = zin.infolist()
        store = {i.filename: zin.read(i.filename) for i in infos}

    stats = {"spacing_clamped": 0, "linesegarray_removed": 0, "cells_merged": 0}
    for name, data in list(store.items()):
        if _SECTION_RE.search(name):
            root = etree.fromstring(data)
            if merge_empty:
                stats["cells_merged"] += merge_trailing_empty_value_cells(root)
            if relax_lines:
                stats["linesegarray_removed"] += strip_linesegarray(root)
            store[name] = etree.tostring(
                root, xml_declaration=True, encoding="UTF-8", standalone=True
            )
        elif _HEADER_RE.search(name) and spacing_floor is not None:
            hroot = etree.fromstring(data)
            stats["spacing_clamped"] += clamp_letter_spacing(hroot, floor=spacing_floor)
            store[name] = etree.tostring(
                hroot, xml_declaration=True, encoding="UTF-8", standalone=True
            )

    with zipfile.ZipFile(out_path, "w") as zout:
        if "mimetype" in store:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, store["mimetype"])
        for info in infos:
            if info.filename == "mimetype":
                continue
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, store[info.filename])
    return stats
