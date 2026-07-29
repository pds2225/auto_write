# -*- coding: utf-8 -*-
"""hwpx_resume_supplement — L086 폼가드·L083 검정·L002 lineseg 편집한정."""
from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import _BlackCharPr, _HP, _q
from auto_write.services.hwpx_resume_supplement import _set_tc_text

_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def test_set_tc_text_strips_lineseg_under_cell_only():
    tc = etree.fromstring(
        f'''<hp:tc xmlns:hp="{_HP}">
          <hp:subList><hp:p>
            <hp:run charPrIDRef="0"><hp:t>~</hp:t></hp:run>
            <hp:linesegarray><hp:lineseg/></hp:linesegarray>
          </hp:p></hp:subList>
        </hp:tc>'''
    )
    sibling = etree.fromstring(
        f'''<hp:p xmlns:hp="{_HP}">
          <hp:run charPrIDRef="0"><hp:t>안내</hp:t></hp:run>
          <hp:linesegarray><hp:lineseg/></hp:linesegarray>
        </hp:p>'''
    )
    wrap = etree.Element("{%s}sec" % "http://www.hancom.co.kr/hwpml/2011/section")
    wrap.append(tc)
    wrap.append(sibling)
    assert _set_tc_text(tc, "서울대") is True
    assert list(tc.iter(_q("linesegarray"))) == []
    assert list(sibling.iter(_q("linesegarray")))  # 형제 보존


def test_set_tc_text_blocks_form_control():
    tc = etree.fromstring(
        f'''<hp:tc xmlns:hp="{_HP}">
          <hp:subList><hp:p><hp:run charPrIDRef="0">
            <hp:checkBtn name="CB" value="UNCHECKED"/><hp:t/>
          </hp:run></hp:p></hp:subList>
        </hp:tc>'''
    )
    assert _set_tc_text(tc, "010") is False


def test_set_tc_text_applies_black_charpr():
    header = etree.fromstring(
        f'''<hh:head xmlns:hh="{_HH}">
          <hh:refList><hh:charProperties itemCnt="1">
            <hh:charPr id="0" textColor="#0000FF"/>
          </hh:charProperties></hh:refList>
        </hh:head>'''
    )
    black = _BlackCharPr(header)
    tc = etree.fromstring(
        f'''<hp:tc xmlns:hp="{_HP}">
          <hp:subList><hp:p>
            <hp:run charPrIDRef="0"><hp:t>~</hp:t></hp:run>
          </hp:p></hp:subList>
        </hp:tc>'''
    )
    assert _set_tc_text(tc, "경력값", black=black) is True
    assert black.changed is True
    run = next(tc.iter(_q("run")))
    assert run.get("charPrIDRef") != "0"
    assert black.is_black(run.get("charPrIDRef"))
