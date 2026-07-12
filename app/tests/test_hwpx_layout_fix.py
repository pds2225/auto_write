# -*- coding: utf-8 -*-
"""hwpx_layout_fix 회귀 테스트 — 자간 하한 clamp / 여러 줄 / 라벨-값 표 병합."""
import io
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from auto_write.services.hwpx_layout_fix import (
    clamp_letter_spacing,
    strip_linesegarray,
    merge_trailing_empty_value_cells,
    force_black_text,
    normalize_colors_in_hwpx,
    finalize_layout_hwpx,
)

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _sec(inner: str):
    xml = f'<hp:sec xmlns:hp="{HP}">{inner}</hp:sec>'
    return etree.fromstring(xml.encode("utf-8"))


def _tc(col, width, text=""):
    body = f"<hp:t>{text}</hp:t>" if text else ""
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="0"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="10"/>'
        f'<hp:subList><hp:p><hp:run>{body}</hp:run></hp:p></hp:subList></hp:tc>'
    )


def _tbl(rows, col_cnt=4):
    trs = "".join(f"<hp:tr>{''.join(r)}</hp:tr>" for r in rows)
    return (
        f'<hp:p><hp:run><hp:tbl colCnt="{col_cnt}" rowCnt="{len(rows)}">'
        f'{trs}</hp:tbl></hp:run></hp:p>'
    )


# --- 1) 자간 하한 clamp -------------------------------------------------------
def test_clamp_letter_spacing_floors_overcompressed():
    hroot = etree.fromstring(
        f'<hh:head xmlns:hh="{HH}"><hh:charPr id="0">'
        f'<hh:spacing hangul="-50" latin="-10" hanja="-30"/>'
        f'</hh:charPr></hh:head>'.encode("utf-8")
    )
    n = clamp_letter_spacing(hroot, floor=-30)
    sp = next(e for e in hroot.iter() if etree.QName(e).localname == "spacing")
    assert sp.get("hangul") == "-30"   # -50 → -30
    assert sp.get("latin") == "-10"    # 완만 → 보존
    assert sp.get("hanja") == "-30"    # 경계값 -30 → 유지
    assert n == 1                       # hangul 1건만 완화


def test_clamp_ignores_nonchar_spacing():
    """charPr 밖 spacing(예: lineseg 줄높이)은 건드리지 않는다."""
    hroot = etree.fromstring(
        f'<hh:head xmlns:hh="{HH}"><hh:lineseg spacing="-99"/></hh:head>'.encode("utf-8")
    )
    assert clamp_letter_spacing(hroot, floor=-30) == 0


# --- 2) 여러 줄(강제 줄 제거) -------------------------------------------------
def test_strip_linesegarray_removes_all():
    sroot = _sec(
        '<hp:p><hp:linesegarray><hp:lineseg/></hp:linesegarray></hp:p>'
        '<hp:p><hp:linesegarray/></hp:p>'
    )
    n = strip_linesegarray(sroot)
    assert n == 2
    assert not [e for e in sroot.iter() if etree.QName(e).localname == "linesegarray"]


# --- 3) 라벨-값 표 병합 -------------------------------------------------------
def test_merge_label_value_table_merges_trailing_empty():
    root = _sec(_tbl([
        [_tc(0, 100, "총 기간"), _tc(1, 200, "2021~2025"), _tc(2, 300), _tc(3, 400)],
        [_tc(0, 100, "건수"), _tc(1, 200, "26건"), _tc(2, 300), _tc(3, 400)],
    ]))
    merged = merge_trailing_empty_value_cells(root)
    assert merged == 2
    q = lambda t: f"{{{HP}}}{t}"
    for tr in root.iter(q("tr")):
        tcs = tr.findall(q("tc"))
        assert len(tcs) == 2  # 라벨 + 값(병합)만 남음
        value = tcs[1]
        assert value.find(q("cellSpan")).get("colSpan") == "3"
        assert value.find(q("cellSz")).get("width") == "900"  # 200+300+400


def test_merge_leaves_real_multicolumn_table_untouched():
    """어느 행이든 뒤쪽 열에 값이 있으면(진짜 다열 표) 병합하지 않는다."""
    root = _sec(_tbl([
        [_tc(0, 100, "기간"), _tc(1, 200, "직장"), _tc(2, 300, "부서"), _tc(3, 400, "담당업무")],
        [_tc(0, 100, "22.11"), _tc(1, 200, "벤처"), _tc(2, 300, "대표"), _tc(3, 400, "경영")],
    ]))
    assert merge_trailing_empty_value_cells(root) == 0
    q = lambda t: f"{{{HP}}}{t}"
    for tr in root.iter(q("tr")):
        assert len(tr.findall(q("tc"))) == 4  # 그대로


def test_merge_skips_when_only_label_column():
    """라벨+값 2열이 안 남으면(1열만 라벨) 병합하지 않는다."""
    root = _sec(_tbl([
        [_tc(0, 100, "라벨"), _tc(1, 200), _tc(2, 300), _tc(3, 400)],
    ], col_cnt=4))
    # 행 1개라 len(rows)<2 로도 걸러짐 → 안전
    assert merge_trailing_empty_value_cells(root) == 0


# --- 4) 파일 진입점 ----------------------------------------------------------
def _make_hwpx(tmp_path: Path) -> Path:
    sec = (
        f'<hp:sec xmlns:hp="{HP}">'
        + _tbl([
            [_tc(0, 100, "총 기간"), _tc(1, 200, "2021~2025"), _tc(2, 300), _tc(3, 400)],
            [_tc(0, 100, "건수"), _tc(1, 200, "26건"), _tc(2, 300), _tc(3, 400)],
        ])
        + '<hp:p><hp:linesegarray><hp:lineseg/></hp:linesegarray></hp:p></hp:sec>'
    )
    hdr = (
        f'<hh:head xmlns:hh="{HH}"><hh:charPr id="0">'
        f'<hh:spacing hangul="-50" latin="0"/></hh:charPr></hh:head>'
    )
    p = tmp_path / "in.hwpx"
    with zipfile.ZipFile(p, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, "application/hwp+zip")
        z.writestr("Contents/section0.xml", sec)
        z.writestr("Contents/header.xml", hdr)
    return p


def test_finalize_layout_hwpx_applies_all(tmp_path):
    inp = _make_hwpx(tmp_path)
    out = tmp_path / "out.hwpx"
    stats = finalize_layout_hwpx(inp, out)
    assert stats["cells_merged"] == 2
    assert stats["linesegarray_removed"] == 1
    assert stats["spacing_clamped"] == 1
    # 결과 파일 열림 + mimetype STORED 보존
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        hroot = etree.fromstring(z.read("Contents/header.xml"))
    sp = next(e for e in hroot.iter() if etree.QName(e).localname == "spacing")
    assert sp.get("hangul") == "-30"


def test_finalize_refuses_overwrite(tmp_path):
    inp = _make_hwpx(tmp_path)
    with pytest.raises(ValueError):
        finalize_layout_hwpx(inp, inp)


# --- 5) 유색 텍스트 검정 정규화 ----------------------------------------------
def test_force_black_text_blacks_only_colored():
    hroot = etree.fromstring(
        f'<hh:head xmlns:hh="{HH}">'
        f'<hh:charPr id="0" textColor="#0000FF"/>'
        f'<hh:charPr id="1" textColor="#FFFFFF"/>'
        f'<hh:charPr id="2" textColor="#000000"/>'
        f'<hh:charPr id="3" textColor="auto"/>'
        f'</hh:head>'.encode("utf-8")
    )
    n = force_black_text(hroot)
    cps = {c.get("id"): c.get("textColor")
           for c in hroot.iter() if etree.QName(c).localname == "charPr"}
    assert cps["0"] == "#000000"   # 파랑 → 검정
    assert cps["1"] == "#FFFFFF"   # 흰색 보존(어두운 칸)
    assert cps["2"] == "#000000"   # 검정 유지
    assert cps["3"] == "auto"      # 비-hex(auto) 보존
    assert n == 1


def test_normalize_colors_in_hwpx_inplace_and_idempotent(tmp_path):
    sec = f'<hp:sec xmlns:hp="{HP}"><hp:p/></hp:sec>'
    hdr = f'<hh:head xmlns:hh="{HH}"><hh:charPr id="0" textColor="#0000FF"/></hh:head>'
    p = tmp_path / "colored.hwpx"
    with zipfile.ZipFile(p, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, "application/hwp+zip")
        z.writestr("Contents/section0.xml", sec)
        z.writestr("Contents/header.xml", hdr)
    assert normalize_colors_in_hwpx(p) == 1
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        hroot = etree.fromstring(z.read("Contents/header.xml"))
    cp = next(c for c in hroot.iter() if etree.QName(c).localname == "charPr")
    assert cp.get("textColor") == "#000000"
    assert normalize_colors_in_hwpx(p) == 0  # 멱등 — 두 번째는 무변경
