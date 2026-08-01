"""test_hwpx_image_clamp.py — L001 회귀: HWPX pic 삽입 폭 클램프·폭 4값 정합 잠금.

app/scripts/patch_profile_v5_visual.py 의 `_make_pic_para` 가 그림을 삽입할 때
표시 폭을 본문폭(46800 HWPUNIT)으로 클램프하고, 원본 폭 쌍(orgSz·imgRect)과
표시 폭 쌍(curSz·sz)을 일관되게 맞추는 규칙을 순수 호출로 재현·단언한다.

계산 규칙(잠금 대상):
  org_w  = width_px * 75            (HWPUNIT)
  disp_w = min(org_w, 46800)        (본문폭 상한 클램프)
  orgSz.width == imgRect.width == org_w    (원본 크기 쌍)
  curSz.width == sz.width      == disp_w   (표시 크기 쌍)
클램프가 없을 때(org_w <= 46800)는 네 값(org/cur/sz/imgRect)이 모두 동일하다.
"""
from __future__ import annotations

from scripts.patch_profile_v5_visual import _HWP_PER_PX, _make_pic_para

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_MAX_BODY_W = 46800  # 본문폭 상한(HWPUNIT)


def _q(t: str) -> str:
    return f"{{{_HP}}}{t}"


def _pic_widths(width_px: int, height_px: int) -> tuple[int, int, int, int]:
    """_make_pic_para 산출물에서 (orgSz, curSz, sz, imgRect) 폭을 읽어온다."""
    p = _make_pic_para("img1", "img1", width_px, height_px, inst_seed=100)
    pic = p.find(".//" + _q("pic"))
    org = int(pic.find(_q("orgSz")).get("width"))
    cur = int(pic.find(_q("curSz")).get("width"))
    sz = int(pic.find(_q("sz")).get("width"))
    rect = pic.find(_q("imgRect"))
    rect_w = max(int(pt.get("x")) for pt in rect)  # pt1/pt2 x = 원본 폭
    return org, cur, sz, rect_w


def test_disp_width_clamped_to_body_width():
    """큰 이미지(org_w > 46800): 표시 폭은 본문폭으로 클램프, 원본 폭은 보존."""
    width_px = 900
    org_w = width_px * _HWP_PER_PX  # 67500 > 46800
    assert org_w > _MAX_BODY_W
    org, cur, sz, rect_w = _pic_widths(width_px, 300)
    disp_w = min(org_w, _MAX_BODY_W)
    assert disp_w == _MAX_BODY_W
    assert org == org_w        # orgSz = 원본 폭 보존
    assert rect_w == org_w     # imgRect = 원본 폭
    assert cur == disp_w       # curSz = 클램프된 표시 폭
    assert sz == disp_w        # sz    = 클램프된 표시 폭


def test_no_clamp_all_four_widths_equal():
    """작은 이미지(org_w <= 46800): 클램프 없음 → org/cur/sz/imgRect 4값 동일."""
    width_px = 400
    org_w = width_px * _HWP_PER_PX  # 30000 <= 46800
    assert org_w <= _MAX_BODY_W
    org, cur, sz, rect_w = _pic_widths(width_px, 300)
    disp_w = min(org_w, _MAX_BODY_W)
    assert disp_w == org_w
    assert org == cur == sz == rect_w == org_w  # 4값 동일 잠금


def test_disp_width_follows_min_rule_at_boundaries():
    """경계(46800=624px) 아래/위에서 disp_w = min(org_w, 46800) 규칙 재현."""
    # 46800 / 75 = 624 px 가 정확한 경계
    for width_px in (100, 623, 624, 625, 1200):
        org_w = width_px * _HWP_PER_PX
        _, cur, sz, _ = _pic_widths(width_px, 200)
        expected = min(org_w, _MAX_BODY_W)
        assert cur == expected, f"curSz width mismatch @ {width_px}px"
        assert sz == expected, f"sz width mismatch @ {width_px}px"
