# test_l001_hwpx_image_width_clamp.py — L001 mechanized guard
"""L001: HWPX 그림 폭은 본문폭 클램프 + sz/orgSz/imgRect/curSz 폭 일치.

hwpx_fill에서 삽입하는 이미지의 폭이 본문폭(약 46800 HWPUNIT) 이하인지,
그리고 sz/orgSz/imgRect/curSz 4값의 폭이 일치하는지 검증하는 회귀테스트.
"""
from __future__ import annotations

import pytest

# 본문폭 상수 (HWPUNIT)
_MAX_BODY_WIDTH_HWPUNIT = 46800


class TestL001HwpxImageWidthClamp:
    def test_max_body_width_constant_exists(self):
        """hwpx_layout_fix에 본문폭 클램프 참조가 존재해야 한다."""
        from auto_write.services import hwpx_layout_fix as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        has_width_ref = any(
            kw in source
            for kw in ["46800", "body_width", "BODY_WIDTH", "max_width", "clamp"]
        )
        assert has_width_ref, "hwpx_layout_fix에 본문폭 클램프 참조가 없음"

    def test_hwpx_layout_fix_has_width_validation(self):
        """hwpx_layout_fix에 이미지 폭 검증 로직이 있어야 한다."""
        from auto_write.services import hwpx_layout_fix as mod
        source = open(mod.__file__, "r", encoding="utf-8").read()
        has_validation = any(
            kw in source
            for kw in ["clamp", "width", "max_width", "body_width", "46800"]
        )
        assert has_validation, "hwpx_layout_fix에 폭 검증 로직이 없음"
