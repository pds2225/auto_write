# -*- coding: utf-8 -*-
"""이력서/프로필 자동작성 — 과거 실패 재발방지 회귀 코퍼스.

2026-07-12 세션에서 박다솜 프로필 작업 중 실제로 겪은 결함들을, 현재(origin/master
2af0bf8, PR #71 반영) 엔진이 재발시키지 않는지 각각 회귀 테스트로 굳힌다.
"실패 최소화" 방향의 안전판 — 이력서 자동작성기가 이 위에서 자란다.

매핑(결함 → 방어 엔진):
  D1 글씨겹침/한 줄 강제 잘림      → hwpx_layout_fix.strip_linesegarray
  D2 rowSpan 병합 어긋남(선 사라짐) → hwpx_layout_fix.validate_table_grid  (L031·v7 실측)
  D3 파란 예시체 상속(유색 잔존)    → hwpx_layout_fix.force_black_text
  D4 유색 auto값 오교정            → force_black_text 가 auto/테마색 보존   (L022)
  D5 라벨-값 표 오른쪽 빈칸        → merge_trailing_empty_value_cells (진짜 다열표 보존)
  D6 홍길동 등 템플릿 placeholder 이름 → (검출기 미구현) resume-autowriter P4+ 과제로 skip 표기
"""
import zipfile

import pytest
from lxml import etree

from auto_write.services.hwpx_layout_fix import (
    strip_linesegarray,
    validate_table_grid,
    force_black_text,
    merge_trailing_empty_value_cells,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _sec(inner: str):
    return etree.fromstring(f'<hp:sec xmlns:hp="{HP}">{inner}</hp:sec>'.encode("utf-8"))


def _cell(col, row, *, colspan=1, rowspan=1, width=100, text=""):
    body = f"<hp:t>{text}</hp:t>" if text else ""
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="{colspan}" rowSpan="{rowspan}"/>'
        f'<hp:cellSz width="{width}" height="10"/>'
        f'<hp:subList><hp:p><hp:run>{body}</hp:run></hp:p></hp:subList></hp:tc>'
    )


def _row(cells):
    return f"<hp:tr>{''.join(cells)}</hp:tr>"


def _table(rows, col_cnt):
    return (f'<hp:tbl colCnt="{col_cnt}" rowCnt="{len(rows)}">'
            f'{"".join(rows)}</hp:tbl>')


def _first_tbl(root):
    return next(e for e in root.iter() if etree.QName(e).localname == "tbl")


# --- D1: 글씨겹침(한 줄 강제 캐시) 재발 방지 ---------------------------------
def test_D1_linesegarray_fully_stripped():
    root = _sec(
        '<hp:p><hp:linesegarray><hp:lineseg/></hp:linesegarray></hp:p>'
        '<hp:p><hp:run><hp:t>값</hp:t></hp:run><hp:linesegarray/></hp:p>'
    )
    removed = strip_linesegarray(root)
    assert removed == 2
    assert not [e for e in root.iter()
                if etree.QName(e).localname == "linesegarray"]


# --- D2: rowSpan 병합 어긋남(선 사라짐) 검출 --------------------------------
def _merge_table(col0_rowspan):
    """col0 라벨셀이 col0_rowspan 만큼 세로병합, col1 은 3행 각각 셀."""
    rows = [
        _row([_cell(0, 0, rowspan=col0_rowspan, text="라벨"), _cell(1, 0, text="a")]),
        _row([_cell(1, 1, text="b")]),
        _row([_cell(1, 2, text="c")]),
    ]
    return _sec(_table(rows, col_cnt=2))


def test_D2_correct_rowspan_tiles_ok():
    tbl = _first_tbl(_merge_table(col0_rowspan=3))   # 3행 전부 커버
    res = validate_table_grid(tbl)
    assert res["ok"] is True
    assert res["empties"] == [] and res["overlaps"] == []


def test_D2_undersized_rowspan_leaves_hole():
    """행 삽입 후 rowSpan 미확장(v7 실측 결함) → (2,0) 미커버로 검출."""
    tbl = _first_tbl(_merge_table(col0_rowspan=2))   # 3행인데 2만 커버
    res = validate_table_grid(tbl)
    assert res["ok"] is False
    assert (2, 0) in res["empties"]                  # 강의분야 행 왼쪽 = 선 사라짐 자리


# --- D3: 파란 예시체 상속(유색 잔존) 검정화 ---------------------------------
def test_D3_colored_example_charpr_blacked():
    hroot = etree.fromstring(
        f'<hh:head xmlns:hh="{HH}">'
        f'<hh:charPr id="0" textColor="#0000FF"/>'
        f'<hh:charPr id="1" textColor="#FFFFFF"/>'
        f'</hh:head>'.encode("utf-8")
    )
    n = force_black_text(hroot)
    colors = {c.get("id"): c.get("textColor")
              for c in hroot.iter() if etree.QName(c).localname == "charPr"}
    assert colors["0"] == "#000000"   # 파랑 예시체 → 검정
    assert colors["1"] == "#FFFFFF"   # 어두운 칸 흰색 보존
    assert n == 1


# --- D4: 유색 auto값 오교정 방지 (L022) --------------------------------------
def test_D4_auto_and_theme_color_preserved():
    hroot = etree.fromstring(
        f'<hh:head xmlns:hh="{HH}">'
        f'<hh:charPr id="0" textColor="auto"/>'
        f'<hh:charPr id="1" textColor="#FF0000"/>'
        f'</hh:head>'.encode("utf-8")
    )
    force_black_text(hroot)
    colors = {c.get("id"): c.get("textColor")
              for c in hroot.iter() if etree.QName(c).localname == "charPr"}
    assert colors["0"] == "auto"      # 정규 6hex 아님 → 절대 안 건드림(L022)
    assert colors["1"] == "#000000"   # 정규 유색만 검정


# --- D5: 라벨-값 표 오른쪽 빈칸 병합 / 진짜 다열표 보존 ----------------------
def test_D5_label_value_trailing_empty_merged():
    rows = [
        _row([_cell(0, 0, width=100, text="총 기간"), _cell(1, 0, width=200, text="2021~2025"),
              _cell(2, 0, width=300), _cell(3, 0, width=400)]),
        _row([_cell(0, 1, width=100, text="건수"), _cell(1, 1, width=200, text="26건"),
              _cell(2, 1, width=300), _cell(3, 1, width=400)]),
    ]
    root = _sec(_table(rows, col_cnt=4))
    merged = merge_trailing_empty_value_cells(root)
    assert merged == 2
    q = lambda t: f"{{{HP}}}{t}"
    for tr in _first_tbl(root).findall(q("tr")):
        tcs = tr.findall(q("tc"))
        assert len(tcs) == 2                                   # 라벨+값만
        assert tcs[1].find(q("cellSpan")).get("colSpan") == "3"
        assert tcs[1].find(q("cellSz")).get("width") == "900"  # 200+300+400
    # 병합 후에도 격자 무결(회귀 결합 검증)
    assert validate_table_grid(_first_tbl(root))["ok"] is True


def test_D5_real_multicolumn_table_untouched():
    rows = [
        _row([_cell(0, 0, text="기간"), _cell(1, 0, text="직장"),
              _cell(2, 0, text="부서"), _cell(3, 0, text="담당업무")]),
        _row([_cell(0, 1, text="22.11"), _cell(1, 1, text="벤처"),
              _cell(2, 1, text="대표"), _cell(3, 1, text="경영")]),
    ]
    root = _sec(_table(rows, col_cnt=4))
    assert merge_trailing_empty_value_cells(root) == 0          # 값 있는 열 = 병합 금지
    q = lambda t: f"{{{HP}}}{t}"
    for tr in _first_tbl(root).findall(q("tr")):
        assert len(tr.findall(q("tc"))) == 4


# --- D6: 템플릿 placeholder 이름(홍길동) — 검출기 미구현 ----------------------
@pytest.mark.skip(reason="placeholder 이름 검출기 미구현 — resume-autowriter P4+ 과제. "
                         "현재는 채움 드라이버가 신원값으로 직접 치환(엔진 회귀 대상 아님).")
def test_D6_placeholder_name_detected():
    ...
