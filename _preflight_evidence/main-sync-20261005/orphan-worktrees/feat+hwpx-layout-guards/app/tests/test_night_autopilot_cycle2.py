# -*- coding: utf-8 -*-
"""L076 charPr append-only · L077 제출회귀 잠금 · L070 양식 diff 게이트."""
from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_charpr_guard import (
    assert_charpr_append_only,
    check_charpr_append_only,
)
from auto_write.services.hwpx_fill import _BlackCharPr, _HP
from auto_write.services.hwpx_form_diff import compare_hwpx_forms
from auto_write.services.submission_regression_check import (
    find_pdf,
    parse_pages_spec,
    parse_text_spec,
    run_checks,
    text_has_value,
)

_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_MIMETYPE = b"application/hwp+zip"


def test_charpr_append_only_ok():
    header = etree.fromstring(
        f'''<hh:head xmlns:hh="{_HH}">
          <hh:refList><hh:charProperties itemCnt="2">
            <hh:charPr id="0" textColor="#000000"/>
            <hh:charPr id="1" textColor="#0000FF"/>
          </hh:charProperties></hh:refList>
        </hh:head>'''
    )
    assert check_charpr_append_only(header) == []
    assert_charpr_append_only(header)  # no raise


def test_charpr_mid_insert_detected():
    header = etree.fromstring(
        f'''<hh:head xmlns:hh="{_HH}">
          <hh:refList><hh:charProperties itemCnt="3">
            <hh:charPr id="0" textColor="#000000"/>
            <hh:charPr id="5" textColor="#000000"/>
            <hh:charPr id="1" textColor="#0000FF"/>
          </hh:charProperties></hh:refList>
        </hh:head>'''
    )
    bad = check_charpr_append_only(header)
    assert bad
    assert any("append-only" in m or "작음" in m for m in bad)


def test_black_charpr_clone_keeps_append_only():
    header = etree.fromstring(
        f'''<hh:head xmlns:hh="{_HH}">
          <hh:refList><hh:charProperties itemCnt="1">
            <hh:charPr id="0" textColor="#0000FF"/>
          </hh:charProperties></hh:refList>
        </hh:head>'''
    )
    black = _BlackCharPr(header)
    new_id = black.black_ref("0")
    assert new_id != "0"
    assert check_charpr_append_only(header) == []


def test_find_pdf_and_text_helpers(tmp_path):
    (tmp_path / "참가신청서_박다솜.pdf").write_bytes(b"%PDF")
    assert find_pdf(str(tmp_path), "참가신청서")
    assert find_pdf(str(tmp_path), "없는서류") is None
    assert parse_pages_spec("신청서=1,계획서=5") == [("신청서", 1), ("계획서", 5)]
    assert parse_text_spec("신청서:홍길동|010") == [("신청서", ["홍길동", "010"])]
    assert text_has_value("홍 길 동", "홍길동")


def test_run_checks_with_injected_pdf(tmp_path):
    (tmp_path / "사업계획서.pdf").write_bytes(b"%PDF")

    class _Doc:
        def __len__(self):
            return 5

        def __iter__(self):
            return iter([])

    result = run_checks(
        directory=str(tmp_path),
        pages="사업계획서=5",
        require_text="사업계획서:핵심문구",
        forbid_text="사업계획서:[확인필요]",
        open_pdf=lambda p: _Doc(),
        pdf_text=lambda p: "핵심문구 본문",
        pdf_image_count=lambda p: 0,
    )
    assert result.fails == 0
    # 금지값이 있으면 fail
    bad = run_checks(
        directory=str(tmp_path),
        forbid_text="사업계획서:[확인필요]",
        open_pdf=lambda p: _Doc(),
        pdf_text=lambda p: "여기 [확인필요] 있음",
    )
    assert bad.fails >= 1


def _mini_hwpx(path: Path, mutual: str, value: str = "") -> None:
    sec = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="2">'
        f'<hp:tr>'
        f'<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>{mutual}</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        f'<hp:tc><hp:cellAddr colAddr="1" rowAddr="0"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>{value}</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        f'</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>'
    ).encode()
    hdr = (
        f'<?xml version="1.0"?><hh:head xmlns:hh="{_HH}">'
        f'<hh:charPr id="0" textColor="#000000"/></hh:head>'
    ).encode()
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", hdr)
        z.writestr("Contents/section0.xml", sec)


def test_form_diff_allows_value_fill_only(tmp_path):
    src = tmp_path / "a.hwpx"
    dst = tmp_path / "b.hwpx"
    _mini_hwpx(src, "상호", "")
    _mini_hwpx(dst, "상호", "도보네비")
    rep = compare_hwpx_forms(src, dst)
    assert rep.form_intact is True
    assert rep.value_fills >= 1


def test_form_diff_flags_phrase_deletion(tmp_path):
    src = tmp_path / "a.hwpx"
    dst = tmp_path / "b.hwpx"
    _mini_hwpx(src, "상호(필수)", "")
    _mini_hwpx(dst, "", "도보네비")  # 라벨 삭제 = 양식 훼손
    rep = compare_hwpx_forms(src, dst)
    assert rep.form_intact is False
    assert rep.form_phrase_drops >= 1 or rep.form_phrase_edits >= 1
