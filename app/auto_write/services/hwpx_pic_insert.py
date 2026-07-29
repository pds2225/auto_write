# -*- coding: utf-8 -*-
"""hwpx_pic_insert — HWPX 그림 삽입·리사이즈(L078 서명 / L088 scaMatrix).

L078: 서명 이미지는 값 칸(tc) 문단 앵커 + treatAsChar=0 + vertRelTo=PARA.
L088: 기존 pic 축소는 scaMatrix(+curSz/sz) 로 — orgSz/imgRect 는 보존.
"""
from __future__ import annotations

from typing import Any, Optional

from lxml import etree

from .hwpx_fill import _local, _q, _strip_linesegarray


def _ensure_pos(pic) -> Any:
    pos = None
    for child in pic:
        if _local(getattr(child, "tag", "")) == "pos":
            pos = child
            break
    if pos is None:
        pos = etree.SubElement(pic, _q("pos"))
    return pos


def force_signature_pos(pic) -> dict[str, str]:
    """L078: 서명 pic 위치 속성 강제 — treatAsChar=0, vertRelTo=PARA, horzRelTo=PARA."""
    pos = _ensure_pos(pic)
    pos.set("treatAsChar", "0")
    pos.set("vertRelTo", "PARA")
    pos.set("horzRelTo", "PARA")
    # PAPER/inline 금지 신호 — 기존 값이 PAPER 면 PARA 로 교체.
    if (pos.get("vertRelTo") or "").upper() == "PAPER":
        pos.set("vertRelTo", "PARA")
    return {
        "treatAsChar": pos.get("treatAsChar", ""),
        "vertRelTo": pos.get("vertRelTo", ""),
        "horzRelTo": pos.get("horzRelTo", ""),
    }


def insert_signature_into_tc(tc, pic_element) -> bool:
    """값 칸 tc 의 첫 문단에 서명 pic 을 붙인다(L078 앵커=값 tc).

    폼 컨트롤 칸·빈 래퍼가 아닌 '값 칸'을 호출자가 고른다고 가정.
    """
    if tc is None or pic_element is None:
        return False
    force_signature_pos(pic_element)
    # 직계/하위 첫 p
    p = None
    for cand in tc.iter(_q("p")):
        p = cand
        break
    if p is None:
        sub = None
        for child in tc:
            if _local(getattr(child, "tag", "")) == "subList":
                sub = child
                break
        if sub is None:
            sub = etree.SubElement(tc, _q("subList"))
        p = etree.SubElement(sub, _q("p"))
    run = etree.SubElement(p, _q("run"))
    run.set("charPrIDRef", "0")
    run.append(pic_element)
    _strip_linesegarray(tc, only_under=[tc])
    return True


def _find_child(parent, name: str):
    for child in parent:
        if _local(getattr(child, "tag", "")) == name:
            return child
    return None


def _find_sca_matrix(pic):
    """renderingInfo 아래 scaMatrix (또는 직계) 탐색."""
    for el in pic.iter():
        if _local(getattr(el, "tag", "")) == "scaMatrix":
            return el
    return None


def resize_hwpx_picture(
    pic,
    *,
    scale: Optional[float] = None,
    target_width: Optional[int] = None,
) -> dict[str, Any]:
    """L088: scaMatrix(+curSz/sz) 로 표시 크기만 변경. orgSz·imgRect 불변.

    scale 또는 target_width(HWPUNIT, orgSz.width 기준) 중 하나 필요.
    """
    org = _find_child(pic, "orgSz")
    if org is None:
        raise ValueError("pic 에 orgSz 없음")
    org_w = int(org.get("width") or 0)
    org_h = int(org.get("height") or 0)
    if org_w <= 0:
        raise ValueError("orgSz.width 가 유효하지 않음")
    if scale is None:
        if target_width is None or target_width <= 0:
            raise ValueError("scale 또는 target_width 필요")
        scale = float(target_width) / float(org_w)
    if scale <= 0:
        raise ValueError("scale 은 양수여야 함")

    # imgRect 스냅샷(불변 검증용)
    rect = _find_child(pic, "imgRect")
    rect_before = None
    if rect is not None:
        rect_before = {k: rect.get(k) for k in ("x0", "y0", "x1", "y1") if rect.get(k) is not None}
        # 일부 양식은 left/right/top/bottom
        for k in ("left", "right", "top", "bottom", "width", "height"):
            if rect.get(k) is not None:
                rect_before[k] = rect.get(k)

    org_before = {"width": org.get("width"), "height": org.get("height")}

    disp_w = int(round(org_w * scale))
    disp_h = int(round(org_h * scale))
    for tag in ("curSz", "sz"):
        el = _find_child(pic, tag)
        if el is None:
            el = etree.SubElement(pic, _q(tag))
        el.set("width", str(disp_w))
        el.set("height", str(disp_h))

    sca = _find_sca_matrix(pic)
    if sca is None:
        # renderingInfo 없으면 직계에 생성
        rend = _find_child(pic, "renderingInfo")
        if rend is None:
            rend = etree.SubElement(pic, _q("renderingInfo"))
        sca = etree.SubElement(rend, _q("scaMatrix"))
    # e1..e6: sx 0 0 0 sy 0
    attrs = ("e1", "e2", "e3", "e4", "e5", "e6")
    vals = (f"{scale:.6f}", "0", "0", "0", f"{scale:.6f}", "0")
    for a, v in zip(attrs, vals):
        sca.set(a, v)

    # 불변 확인
    if org.get("width") != org_before["width"] or org.get("height") != org_before["height"]:
        raise RuntimeError("L088 위반: orgSz 가 변경됨")
    if rect is not None and rect_before is not None:
        for k, v in rect_before.items():
            if rect.get(k) != v:
                raise RuntimeError(f"L088 위반: imgRect.{k} 가 변경됨")

    return {
        "scale": scale,
        "org_w": org_w,
        "org_h": org_h,
        "disp_w": disp_w,
        "disp_h": disp_h,
        "orgSz_preserved": True,
        "imgRect_preserved": rect is None or True,
    }
