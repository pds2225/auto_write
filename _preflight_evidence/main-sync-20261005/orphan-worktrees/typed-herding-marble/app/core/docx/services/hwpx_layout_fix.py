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

import os
import re
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

__all__ = [
    "clamp_letter_spacing",
    "strip_linesegarray",
    "relax_forced_single_line",
    "merge_trailing_empty_value_cells",
    "table_width_from_colspan1",
    "force_black_text",
    "normalize_colors_in_hwpx",
    "validate_table_grid",
    "repair_table_grid",
    "repair_all_table_grids",
    "check_hwpx_semantics",
    "finalize_layout_hwpx",
    "DEFAULT_SPACING_FLOOR",
]

# 정규 6자리 hex 색만 유색 판정(hwpx_acceptance.count_colored_charpr 와 동일 기준)
_HEX6_RE = re.compile(r"^[0-9a-fA-F]{6}$")

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


# --- 1b) 유색 텍스트 검정 정규화 --------------------------------------------
def force_black_text(header_root, *, preserve=("FFFFFF",)) -> int:
    """header.xml charPr textColor 가 유색이면 검정(#000000)으로.

    유색 판정은 hwpx_acceptance.count_colored_charpr 와 동일 — 정규 6자리 hex 이고
    흰(FFFFFF)·검정(000000)이 아닐 때만. preserve 색(기본 흰색=어두운 칸용)은 보존.
    hwpx_fill 의 '검정 클론'(채운 값 전용, 기존 미수정)과 달리 여기서는 잔존 예시
    유색체(채우지 않은 안내문구)를 실제로 검정화한다 — 제출본 검정 원칙.
    반환: 검정으로 바꾼 charPr 수.
    """
    keep = {c.upper().lstrip("#") for c in preserve} | {"000000"}
    n = 0
    for cp in header_root.iter():
        if _ln(cp) != "charPr":
            continue
        raw = (cp.get("textColor") or "").lstrip("#")
        if _HEX6_RE.match(raw) and raw.upper() not in keep:
            cp.set("textColor", "#000000")
            n += 1
    return n


def normalize_colors_in_hwpx(path) -> int:
    """hwpx 의 header.xml 유색 charPr 를 검정으로(제자리·원자적 교체). 반환: 교정 수.

    제출 파이프라인(hwpx_submit)에서 채움 직후 호출해, 채우지 않은 예시 유색체를
    검정으로 만들어 수용검사(colored) 를 통과시킨다. 색 변경이 0이면 파일을 건드리지
    않는다(멱등·무변경 시 no-op).
    """
    path = Path(path)
    with zipfile.ZipFile(path) as zin:
        infos = zin.infolist()
        store = {i.filename: zin.read(i.filename) for i in infos}
    hname = next((n for n in store if _HEADER_RE.search(n)), None)
    if hname is None:
        return 0
    hroot = etree.fromstring(store[hname])
    changed = force_black_text(hroot)
    if changed == 0:
        return 0
    store[hname] = etree.tostring(
        hroot, xml_declaration=True, encoding="UTF-8", standalone=True
    )
    fd, tmp = tempfile.mkstemp(suffix=".hwpx", dir=str(path.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
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
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return changed


# --- 2) 한 줄 강제 해제(여러 줄 재계산) ---------------------------------------
def strip_linesegarray(section_root, *, only_under=None) -> int:
    """줄위치 캐시(hp:linesegarray) 제거 → 한글이 열 때 줄위치·줄바꿈 재계산.

    L074: ``only_under`` 지정 시 그 하위만(안내박스 등 미편집 영역 보존).
    """
    from .hwpx_fill import _strip_linesegarray
    return _strip_linesegarray(section_root, only_under=only_under)


# 사용자 표현("여러 줄로 작성") 기준 별칭
relax_forced_single_line = strip_linesegarray


def table_width_from_colspan1(tbl) -> dict:
    """L091: 표 실제 폭 = colSpan==1 셀들의 열별 폭 합.

    병합 제목 셀(colSpan>1) 폭은 열 폭으로 쓰지 않는다(표 깨짐 방지).
    반환: {width, col_widths: {colAddr: w}, skipped_merged: n, ok: bool}.
    """
    col_widths: dict[int, int] = {}
    skipped = 0
    for tc in list(tbl.iter()):
        if _ln(tc) != "tc":
            continue
        # 중첩 표의 셀은 제외 — 직계 행 소속만(가장 가까운 조상 tbl 이 자신).
        parent_tbl = tc.getparent()
        while parent_tbl is not None and _ln(parent_tbl) != "tbl":
            parent_tbl = parent_tbl.getparent()
        if parent_tbl is not tbl:
            continue
        span = _tc_span(tc, "colSpan")
        if span != 1:
            skipped += 1
            continue
        col = _tc_col(tc)
        w = _tc_width(tc)
        if col < 0 or w <= 0:
            continue
        # 같은 열의 첫 유효 폭 채택(헤더·데이터 행 혼재 시 안정)
        if col not in col_widths:
            col_widths[col] = w
    total = sum(col_widths[c] for c in sorted(col_widths))
    return {
        "width": total,
        "col_widths": dict(col_widths),
        "skipped_merged": skipped,
        "ok": bool(col_widths) and total > 0,
    }


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


# --- 격자 타일링 검증(rowSpan/colSpan 병합 정합) --------------------------------
def _tc_row(tc) -> int:
    a = _child(tc, "cellAddr")
    if a is None:
        return -1
    try:
        return int(a.get("rowAddr", "-1"))
    except (TypeError, ValueError):
        return -1


def validate_table_grid(tbl) -> dict:
    """표 격자 타일링 검증 — 모든 tc의 (rowAddr,colAddr)×(rowSpan,colSpan)이
    rowCnt×colCnt 를 겹침0·공백0으로 정확히 덮는가.

    행 삽입 후 세로병합 rowSpan 을 안 늘리면(실측 v7 결함: 전문분야 칸 → 선 사라짐)
    그 열 일부가 미커버(empties)로 잡힌다. 중첩 표는 세지 않는다(직계 tr>tc 만).
    반환: {"ok", "overlaps":[(r,c)], "empties":[(r,c)], "oob":[...], "rows", "cols"}.
    """
    try:
        R = int(tbl.get("rowCnt") or "0")
        C = int(tbl.get("colCnt") or "0")
    except (TypeError, ValueError):
        return {"ok": False, "overlaps": [], "empties": [], "oob": [],
                "rows": 0, "cols": 0, "error": "rowCnt/colCnt 파싱 실패"}
    if R <= 0 or C <= 0:
        return {"ok": False, "overlaps": [], "empties": [], "oob": [],
                "rows": R, "cols": C, "error": "rowCnt/colCnt 0"}
    grid = [[0] * C for _ in range(R)]
    overlaps: list = []
    oob: list = []
    for tr in tbl:
        if _ln(tr) != "tr":
            continue
        for tc in tr:
            if _ln(tc) != "tc":
                continue
            r0, c0 = _tc_row(tc), _tc_col(tc)
            if r0 < 0 or c0 < 0:
                continue
            rs = _tc_span(tc, "rowSpan")
            cs = _tc_span(tc, "colSpan")
            for r in range(r0, r0 + rs):
                for c in range(c0, c0 + cs):
                    if r >= R or c >= C:
                        oob.append((r0, c0, rs, cs))
                        continue
                    grid[r][c] += 1
                    if grid[r][c] > 1:
                        overlaps.append((r, c))
    empties = [(r, c) for r in range(R) for c in range(C) if grid[r][c] == 0]
    return {"ok": not overlaps and not oob and not empties,
            "overlaps": overlaps, "empties": empties, "oob": oob,
            "rows": R, "cols": C}


def repair_table_grid(tbl) -> dict:
    """격자가 깨진 표(rowAddr/colAddr 오지정)를 물리 순서로 재주소화해 고친다.

    실측(박다솜 프로필 v3~v7): 수행 표 마지막 행 rowAddr 가 2로 중복 지정돼 한 행이
    겹치고 다른 행이 비어 한글이 문서 열기를 거부했다(채움 스크립트가 행 추가 시 rowAddr
    미증가). 원인: 각 tr 의 cellAddr rowAddr/colAddr 가 물리 위치와 어긋남.

    **안전 규칙**: 병합(rowSpan/colSpan>1)이 있는 표는 자동 교정하지 않는다(정상 병합을
    깨뜨릴 위험 — 그런 표는 needs 사람확인). 이미 정상인 표는 건드리지 않는다(멱등).
    1x1 셀만 있는 표에 한해 각 tr 의 cellAddr 를 (tr 순서, 셀 순서)로 재지정한다.

    반환: {"repaired": bool, "cells_fixed": int, "skipped_merge": bool}.
    """
    if validate_table_grid(tbl).get("ok"):
        return {"repaired": False, "cells_fixed": 0, "skipped_merge": False}
    trs = [tr for tr in tbl if _ln(tr) == "tr"]
    has_merge = any(
        _tc_span(tc, "rowSpan") != 1 or _tc_span(tc, "colSpan") != 1
        for tr in trs for tc in tr if _ln(tc) == "tc")
    if has_merge:
        return {"repaired": False, "cells_fixed": 0, "skipped_merge": True}
    cells_fixed = 0
    for ri, tr in enumerate(trs):
        ci = 0
        for tc in tr:
            if _ln(tc) != "tc":
                continue
            addr = _child(tc, "cellAddr")
            if addr is not None:
                if addr.get("rowAddr") != str(ri):
                    addr.set("rowAddr", str(ri)); cells_fixed += 1
                if addr.get("colAddr") != str(ci):
                    addr.set("colAddr", str(ci)); cells_fixed += 1
            ci += 1
    return {"repaired": validate_table_grid(tbl).get("ok", False),
            "cells_fixed": cells_fixed, "skipped_merge": False}


def repair_all_table_grids(section_root) -> int:
    """섹션 내 모든 표의 깨진 격자를 자동 교정한다. 교정된 셀 수를 반환한다.

    한글이 못 여는 '깨진 격자 hwpx' 가 생성·제출 경로로 나가지 않게 하는 최종 방어선.
    병합 있는 표는 건드리지 않으므로 정상 문서엔 무해(멱등)하다."""
    fixed = 0
    for el in section_root.iter():
        if _ln(el) == "tbl":
            fixed += repair_table_grid(el)["cells_fixed"]
    return fixed


# --- 파일 진입점 -------------------------------------------------------------
def finalize_layout_hwpx(
    in_path,
    out_path,
    *,
    spacing_floor: int | None = DEFAULT_SPACING_FLOOR,
    relax_lines: bool = True,
    merge_empty: bool = True,
    repair_grid: bool = True,
) -> dict:
    """채워진 HWPX 에 레이아웃 정규화 3종을 적용해 out_path 로 저장. 원본 보존.

    repair_grid=True(기본): 표 격자가 깨진(rowAddr/colAddr 오지정) 표를 자동 교정해
    한글이 못 여는 hwpx 가 나가지 않게 한다(병합 있는 표는 건드리지 않아 무해·멱등)."""
    in_path, out_path = Path(in_path), Path(out_path)
    if in_path.resolve() == out_path.resolve():
        raise ValueError("원본 덮어쓰기 금지: 출력 경로가 입력과 같습니다.")

    with zipfile.ZipFile(in_path) as zin:
        infos = zin.infolist()
        store = {i.filename: zin.read(i.filename) for i in infos}

    stats = {"spacing_clamped": 0, "linesegarray_removed": 0, "cells_merged": 0,
             "grid_cells_fixed": 0}
    for name, data in list(store.items()):
        if _SECTION_RE.search(name):
            root = etree.fromstring(data)
            if repair_grid:
                stats["grid_cells_fixed"] += repair_all_table_grids(root)
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


def check_hwpx_semantics(path) -> dict:
    """hwpx 가 한글에서 열리는 데 필요한 '의미 규칙' 검사(구문 유효성 넘어).

    한글은 zip/XML 이 멀쩡해도 ①itemCnt 불일치 ②정의 없는 ID 참조(charPr 등)
    ③표 격자 깨짐(rowAddr/colAddr 충돌) 이면 문서 열기를 거부한다. 실측(박다솜 v7)
    에서 표 격자 결함으로 '안 열림' 이 재현·확인됐다. 읽기 전용.

    반환: {"ok", "itemcnt_issues":[...], "dangling_refs":[(attr,id)...],
           "broken_tables":[{index,rows,cols,overlaps,empties,oob}...], "section_count"}.
    """
    path = Path(path)
    z = zipfile.ZipFile(path)
    names = z.namelist()
    defined: set = set()
    itemcnt_issues: list = []
    for hn in [n for n in names if _HEADER_RE.search(n)]:
        hroot = etree.fromstring(z.read(hn))
        for el in hroot.iter():
            cnt = el.get("itemCnt")
            if cnt is None:
                continue
            idk = [c for c in el if c.get("id") is not None]
            for c in idk:
                defined.add(c.get("id"))
            try:
                if idk and int(cnt) != len(idk):
                    itemcnt_issues.append(f"{_ln(el)}: itemCnt={cnt} 실제={len(idk)}")
            except (TypeError, ValueError):
                pass
    ref_attrs = {"charPrIDRef", "paraPrIDRef", "styleIDRef", "borderFillIDRef"}
    dangling: set = set()
    broken: list = []
    sec_count = 0
    for sn in [n for n in names if _SECTION_RE.search(n)]:
        sec_count += 1
        sroot = etree.fromstring(z.read(sn))
        for el in sroot.iter():
            for a, v in el.attrib.items():
                if a.split("}")[-1] in ref_attrs and v not in defined:
                    dangling.add((a.split("}")[-1], v))
        ti = 0
        for el in sroot.iter():
            if _ln(el) == "tbl":
                ti += 1
                r = validate_table_grid(el)
                if not r.get("ok"):
                    broken.append({
                        "index": ti, "rows": r.get("rows"), "cols": r.get("cols"),
                        "overlaps": len(r.get("overlaps", [])),
                        "empties": len(r.get("empties", [])),
                        "oob": len(r.get("oob", [])),
                    })
    return {
        "ok": not itemcnt_issues and not dangling and not broken,
        "itemcnt_issues": itemcnt_issues,
        "dangling_refs": sorted(dangling)[:20],
        "broken_tables": broken,
        "section_count": sec_count,
    }
