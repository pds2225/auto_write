# -*- coding: utf-8 -*-
"""야간 high 갭 L074·L075·L078·L087·L088·L089·L091 기계화 회귀."""
from __future__ import annotations

from lxml import etree

from auto_write.services import hwp_com_fill
from auto_write.services.hwp_com_fill import find_cancel_insert_text
from auto_write.services.hwpx_fill import _HP, _q
from auto_write.services.hwpx_layout_fix import table_width_from_colspan1
from auto_write.services.hwpx_pic_insert import (
    force_signature_pos,
    insert_signature_into_tc,
    resize_hwpx_picture,
)
from auto_write.services.hwpx_section_split import (
    assert_pagepr_unchanged,
    find_first_secpr_paragraph,
    recycle_first_secpr_paragraph,
)
from auto_write.services.submission_regression_check import (
    compare_to_baseline,
    run_checks,
)

_HS = "http://www.hancom.co.kr/hwpml/2011/section"


# --- L075 ------------------------------------------------------------------- #


def test_compare_to_baseline_pages_text_images(tmp_path):
    cur = tmp_path / "cur"
    base = tmp_path / "base"
    cur.mkdir()
    base.mkdir()
    (cur / "신청서.pdf").write_bytes(b"%PDF")
    (base / "신청서.pdf").write_bytes(b"%PDF")

    class _Doc:
        def __len__(self):
            return 2

        def __iter__(self):
            return iter([])

    ok = compare_to_baseline(
        current_dir=str(cur),
        baseline_dir=str(base),
        keys="신청서",
        open_pdf=lambda p: _Doc(),
        pdf_text=lambda p: "확정본 본문 내용입니다" * 5,
        pdf_image_count=lambda p: 1,
        check_bold=False,
    )
    assert ok.fails == 0

    # 페이지 회귀
    class _Short:
        def __len__(self):
            return 1

        def __iter__(self):
            return iter([])

    bad = compare_to_baseline(
        current_dir=str(cur),
        baseline_dir=str(base),
        keys="신청서",
        open_pdf=lambda p: _Short() if "cur" in p.replace("\\", "/") else _Doc(),
        pdf_text=lambda p: "짧음",
        pdf_image_count=lambda p: 0 if "cur" in p.replace("\\", "/") else 1,
        check_bold=False,
    )
    assert bad.fails >= 1


def test_run_checks_baseline_dir_wired(tmp_path):
    cur = tmp_path / "cur"
    base = tmp_path / "base"
    cur.mkdir()
    base.mkdir()
    (cur / "계획서.pdf").write_bytes(b"%PDF")
    (base / "계획서.pdf").write_bytes(b"%PDF")

    class _Doc:
        def __len__(self):
            return 3

        def __iter__(self):
            return iter([])

    result = run_checks(
        directory=str(cur),
        baseline_dir=str(base),
        baseline_keys="계획서",
        open_pdf=lambda p: _Doc(),
        pdf_text=lambda p: "본문" * 20,
        pdf_image_count=lambda p: 0,
    )
    assert any("이월" in line for line in result.lines)
    assert result.fails == 0


# --- L078 / L088 ------------------------------------------------------------ #


def _make_pic(*, treat="1", vert="PAPER", w=1000, h=500) -> etree._Element:
    pic = etree.Element(_q("pic"))
    pos = etree.SubElement(pic, _q("pos"))
    pos.set("treatAsChar", treat)
    pos.set("vertRelTo", vert)
    pos.set("horzRelTo", "PARA")
    org = etree.SubElement(pic, _q("orgSz"))
    org.set("width", str(w))
    org.set("height", str(h))
    rect = etree.SubElement(pic, _q("imgRect"))
    rect.set("x0", "0")
    rect.set("y0", "0")
    rect.set("x1", str(w))
    rect.set("y1", str(h))
    rend = etree.SubElement(pic, _q("renderingInfo"))
    sca = etree.SubElement(rend, _q("scaMatrix"))
    for a, v in zip(("e1", "e2", "e3", "e4", "e5", "e6"), ("1", "0", "0", "0", "1", "0")):
        sca.set(a, v)
    return pic


def test_force_signature_pos_para_not_paper():
    pic = _make_pic()
    out = force_signature_pos(pic)
    assert out["treatAsChar"] == "0"
    assert out["vertRelTo"] == "PARA"
    assert out["horzRelTo"] == "PARA"


def test_insert_signature_into_value_tc():
    tc = etree.fromstring(
        f'<hp:tc xmlns:hp="{_HP}">'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>신청인</hp:t></hp:run></hp:p></hp:subList>'
        f"</hp:tc>"
    )
    pic = _make_pic()
    assert insert_signature_into_tc(tc, pic) is True
    pics = [el for el in tc.iter(_q("pic"))]
    assert len(pics) == 1
    pos = [c for c in pics[0] if c.tag.endswith("pos")][0]
    assert pos.get("treatAsChar") == "0"
    assert pos.get("vertRelTo") == "PARA"


def test_resize_hwpx_picture_preserves_org_and_imgrect():
    pic = _make_pic(w=2000, h=1000)
    org_before = {k: pic.find(_q("orgSz")).get(k) for k in ("width", "height")}
    rect_before = {k: pic.find(_q("imgRect")).get(k) for k in ("x0", "y0", "x1", "y1")}
    info = resize_hwpx_picture(pic, scale=0.5)
    assert info["disp_w"] == 1000
    assert info["disp_h"] == 500
    assert {k: pic.find(_q("orgSz")).get(k) for k in ("width", "height")} == org_before
    assert {k: pic.find(_q("imgRect")).get(k) for k in ("x0", "y0", "x1", "y1")} == rect_before
    sca = pic.find(f".//{{{_HP}}}scaMatrix")
    assert float(sca.get("e1")) == 0.5
    assert float(sca.get("e5")) == 0.5
    cur = pic.find(_q("curSz"))
    assert cur is not None and cur.get("width") == "1000"


# --- L087 ------------------------------------------------------------------- #


class _MockFindHwp:
    def __init__(self, found=True):
        self.found = found
        self.calls: list[str] = []
        self.inserted: list[str] = []

    def FindText(self, text, *a):  # noqa: N802
        self.calls.append(f"FindText:{text}")
        return self.found

    def Cancel(self):  # noqa: N802
        self.calls.append("Cancel")

    def InsertText(self, text):  # noqa: N802
        self.calls.append(f"InsertText:{text}")
        self.inserted.append(text)


def test_find_cancel_insert_order():
    hwp = _MockFindHwp(found=True)
    rep = find_cancel_insert_text(hwp, "(인)", "박다솜")
    assert rep["ok"] and rep["cancelled"] and rep["inserted"]
    assert hwp.calls == ["FindText:(인)", "Cancel", "InsertText:박다솜"]
    assert hwp.inserted == ["박다솜"]


def test_find_cancel_insert_skips_when_not_found():
    hwp = _MockFindHwp(found=False)
    rep = find_cancel_insert_text(hwp, "없는글자", "X")
    assert rep["ok"] is False and rep["inserted"] is False
    assert "InsertText" not in "".join(hwp.calls)


def test_find_cancel_insert_aborts_without_cancel():
    class _NoCancel:
        def FindText(self, text, *a):  # noqa: N802
            return True

        def InsertText(self, text):  # noqa: N802
            raise AssertionError("Cancel 없이 Insert 하면 안 됨")

    rep = find_cancel_insert_text(_NoCancel(), "a", "b")
    assert rep["ok"] is False and rep["cancelled"] is False


# --- L089 ------------------------------------------------------------------- #


def test_recycle_first_secpr_paragraph_keeps_pagepr():
    root = etree.fromstring(
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p>'
        f'<hp:secPr><hp:pagePr width="59528" height="84188" landscape="0">'
        f'<hp:margin left="8504" right="8504" top="5668" bottom="4252"/>'
        f"</hp:pagePr></hp:secPr>"
        f'<hp:run charPrIDRef="0"><hp:t>공고 본문 — 삭제 대상</hp:t></hp:run>'
        f"</hp:p>"
        f'<hp:p><hp:run charPrIDRef="0"><hp:t>서식 표</hp:t></hp:run></hp:p>'
        f"</hs:sec>"
    )
    before = recycle_first_secpr_paragraph(root)
    assert before["ok"] and before["recycled"]
    assert before["page_pr_snapshot"].get("pagePr.width") == "59528"
    p0 = find_first_secpr_paragraph(root)
    assert p0 is not None
    # 본문 run 제거됨, secPr 잔존
    texts = [t.text for t in p0.iter(_q("t")) if t.text]
    assert texts == []
    assert assert_pagepr_unchanged(before["page_pr_snapshot"], root) == []


# --- L091 ------------------------------------------------------------------- #


def test_table_width_from_colspan1_ignores_merged_title():
    # 열폭 1000+2000=3000. 제목 병합셀 폭 9999 은 무시.
    tbl = etree.fromstring(
        f'<hp:tbl xmlns:hp="{_HP}" rowCnt="2" colCnt="2">'
        f"<hp:tr>"
        f'<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        f'<hp:cellSpan colSpan="2" rowSpan="1"/>'
        f'<hp:cellSz width="9999" height="100"/>'
        f"<hp:subList><hp:p/></hp:subList></hp:tc>"
        f"</hp:tr>"
        f"<hp:tr>"
        f'<hp:tc><hp:cellAddr colAddr="0" rowAddr="1"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="1000" height="100"/>'
        f"<hp:subList><hp:p/></hp:subList></hp:tc>"
        f'<hp:tc><hp:cellAddr colAddr="1" rowAddr="1"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="2000" height="100"/>'
        f"<hp:subList><hp:p/></hp:subList></hp:tc>"
        f"</hp:tr>"
        f"</hp:tbl>"
    )
    info = table_width_from_colspan1(tbl)
    assert info["ok"]
    assert info["width"] == 3000
    assert info["skipped_merged"] == 1
    assert info["col_widths"] == {0: 1000, 1: 2000}


# silence unused import lint for re-export smoke
assert hwp_com_fill.find_cancel_insert_text is find_cancel_insert_text


def test_resize_hwpx_picture_keeps_display_aspect_when_orgsz_wrong():
    """orgSz 비율이 실제 그림과 어긋난 양식에서 그림이 납작해지면 안 된다.

    실측(달구벌 신청서 서명): orgSz 80.4x4.3mm 인데 화면 표시는 5.7x4.5mm.
    orgSz 비율로 세로를 계산하면 15mm 로 키울 때 0.8mm 로 눌린다.
    """
    pic = _make_pic(w=22800, h=1219)          # orgSz 비율 약 18.7:1 (어긋남)
    for tag in ("sz", "curSz"):               # 실제 표시 크기 1.27:1
        el = etree.SubElement(pic, _q(tag))
        el.set("width", "1616")
        el.set("height", "1276")

    info = resize_hwpx_picture(pic, target_width=4252)   # 15mm 로 확대

    assert info["disp_w"] == 4252
    assert 3300 < info["disp_h"] < 3400       # 표시 비율 유지(≈3357), 눌림(227) 아님
    sca = [el for el in pic.iter() if el.tag.endswith("scaMatrix")][0]
    assert sca.get("e1") != sca.get("e5")     # 가로·세로 배율을 따로 계산
