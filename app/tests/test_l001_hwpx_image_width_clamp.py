# test_l001_hwpx_image_width_clamp.py — L001 / L142 mechanized guard
"""L001 / L142: 그림 표시 크기는 너비뿐 아니라 높이도 본다.

실측: 2026-06-15 박다솜 프로필 hwpx 사진이 칸을 넘침.
가드: picture_display_wh 가 sz(없으면 curSz) 가로·세로를 둘 다 >0 으로 요구하고,
resize_hwpx_picture 가 리사이즈 직후 그 값을 읽는다.
폭 클램프(46800)는 test_hwpx_image_clamp.py. 픽셀 눈검증은 L005(judgment).
"""
from __future__ import annotations

import pytest
from lxml import etree

from auto_write.services.hwpx_fill import _q
from auto_write.services.hwpx_pic_insert import picture_display_wh, resize_hwpx_picture


def _pic(*, sz_w: str = "4000", sz_h: str | None = "5000") -> etree._Element:
    pic = etree.Element(_q("pic"))
    sz = etree.SubElement(pic, _q("sz"))
    sz.set("width", sz_w)
    if sz_h is not None:
        sz.set("height", sz_h)
    org = etree.SubElement(pic, _q("orgSz"))
    org.set("width", "4000")
    org.set("height", "5000")
    return pic


def test_l001_picture_display_wh_requires_height() -> None:
    assert picture_display_wh(_pic(sz_h="5000")) == (4000, 5000)
    with pytest.raises(ValueError, match="가로·세로"):
        picture_display_wh(_pic(sz_h="0"))
    with pytest.raises(ValueError, match="가로·세로"):
        picture_display_wh(_pic(sz_w="0", sz_h="5000"))
    pic = etree.Element(_q("pic"))
    with pytest.raises(ValueError, match="sz/curSz"):
        picture_display_wh(pic)


def test_l001_resize_reads_height_via_picture_display_wh() -> None:
    pic = _pic(sz_w="2000", sz_h="2500")
    info = resize_hwpx_picture(pic, scale=0.5)
    assert info["disp_w"] > 0 and info["disp_h"] > 0
    assert picture_display_wh(pic) == (info["disp_w"], info["disp_h"])
    pic.find(_q("sz")).set("height", "0")
    with pytest.raises(ValueError, match="가로·세로"):
        picture_display_wh(pic)
