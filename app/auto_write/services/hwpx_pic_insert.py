# -*- coding: utf-8 -*-
"""hwpx_pic_insert — HWPX 그림 삽입·리사이즈(L078 서명 / L088 scaMatrix).

L078: 서명 이미지는 값 칸(tc) 문단 앵커 + treatAsChar=0 + vertRelTo=PARA.
L088: 기존 pic 축소는 scaMatrix(+curSz/sz) 로 — orgSz/imgRect 는 보존.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

from lxml import etree

from .hwpx_fill import _inline_texts, _local, _q, _strip_linesegarray


_HWPUNIT_PER_PX = 7200 / 96      # 96dpi 기준 픽셀 → HWPUNIT
_HWPUNIT_PER_MM = 7200 / 25.4


def _px_size(path: Path) -> tuple[int, int]:
    """이미지 픽셀 크기 — PNG/JPEG 헤더만 읽는다(외부 라이브러리 불필요)."""
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:3] == b"\xff\xd8\xff":                      # JPEG: SOFn 세그먼트 탐색
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker, seglen = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return (int.from_bytes(data[i + 7:i + 9], "big"),
                        int.from_bytes(data[i + 5:i + 7], "big"))
            i += 2 + seglen
    raise ValueError(f"픽셀 크기를 읽을 수 없습니다(PNG/JPEG 만 지원): {path}")


def _next_image_id(hpf_text: str) -> int:
    used = [int(m) for m in re.findall(r'id="image(\d+)"', hpf_text)]
    return (max(used) + 1) if used else 1


def build_picture_element(donor, *, image_id: str, px: tuple[int, int],
                          width_mm: float, comment: str = ""):
    """기존 그림(donor)을 복제해 '새 이미지를 가리키는' hp:pic 을 만든다.

    양식이 이미 쓰고 있는 그림 XML을 그대로 베끼기 때문에, 한글이 요구하는 속성
    (rendering/imgClip/effects 등)을 빠뜨릴 위험이 없다. 바꾸는 것은 참조 이미지·
    크기·설명뿐이다.
    """
    pic = copy.deepcopy(donor)
    pw, ph = px
    org_w = int(round(pw * _HWPUNIT_PER_PX))
    org_h = int(round(ph * _HWPUNIT_PER_PX))
    disp_w = int(round(width_mm * _HWPUNIT_PER_MM))
    disp_h = int(round(disp_w * ph / pw))
    scale = disp_w / org_w if org_w else 1.0

    for name, w, h in (("orgSz", org_w, org_h), ("curSz", disp_w, disp_h),
                       ("sz", disp_w, disp_h)):
        el = _find_child(pic, name)
        if el is None:
            el = etree.SubElement(pic, _q(name))
        el.set("width", str(w))
        el.set("height", str(h))

    rect = _find_child(pic, "imgRect")
    if rect is not None:
        for idx, (x, y) in enumerate(((0, 0), (org_w, 0), (org_w, org_h), (0, org_h))):
            pt = _find_child(rect, f"pt{idx}")
            if pt is not None:
                pt.set("x", str(x))
                pt.set("y", str(y))

    sca = _find_sca_matrix(pic)
    if sca is not None:
        for attr, val in zip(("e1", "e2", "e3", "e4", "e5", "e6"),
                             (f"{scale:.6f}", "0", "0", "0", f"{scale:.6f}", "0")):
            sca.set(attr, val)

    for el in pic.iter():
        if _local(getattr(el, "tag", "")) == "img":
            el.set("binaryItemIDRef", image_id)
            break

    pos = _ensure_pos(pic)
    pos.set("treatAsChar", "1")          # 글자처럼 취급 = 표 칸 안에서 안전하게 흐름
    for key in ("id", "instid"):
        if pic.get(key) is not None:
            pic.set(key, str(abs(hash((image_id, key))) % 2_000_000_000))
    sc = _find_child(pic, "shapeComment")
    if sc is not None:
        sc.text = comment or f"그림입니다. ({pw}x{ph} pixel)"
    return pic


def add_pictures_to_hwpx(in_hwpx, out_hwpx, pictures: list[dict]) -> dict[str, Any]:
    """HWPX 에 새 그림을 넣는다 — 양식·기존 내용은 그대로 두고 그림만 추가.

    pictures 항목: ``{"path": png/jpg, "anchor": "넣을 자리를 찾을 문단 글",
    "width_mm": 150, "comment": "설명", "into_next": True}``
    ``into_next`` 가 True 면 앵커 문단의 **다음 빈 문단**에 넣는다(캡션 아래 배치).

    안전 규칙: 앵커는 문서에서 유일해야 하고(아니면 건너뜀), 원본은 읽기만 하며,
    mimetype 선두·무압축을 유지해 HWPX 유효성을 지킨다.
    """
    src, dst = Path(in_hwpx), Path(out_hwpx)
    if src.resolve() == dst.resolve():
        raise ValueError("출력이 입력과 같습니다. 원본 덮어쓰기는 금지입니다.")
    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        data = {i.filename: zin.read(i.filename) for i in infos}

    hpf_name = "Contents/content.hpf"
    hpf = data[hpf_name].decode("utf-8")
    sec_name = next(n for n in sorted(data) if re.match(r"Contents/section\d+\.xml$", n))
    root = etree.fromstring(data[sec_name])

    donor = next((p for p in root.iter(_q("pic"))), None)
    if donor is None:
        raise ValueError("복제할 기존 그림이 없습니다(도너 부재).")

    report: dict[str, Any] = {"added": [], "skipped": []}
    next_id = _next_image_id(hpf)
    added_entries: list[tuple[str, bytes]] = []

    for spec in pictures:
        path = Path(spec["path"])
        anchor = str(spec.get("anchor") or "")
        # 표를 감싸는 바깥 문단은 표 안 글자를 전부 흡수해 앵커가 중복으로 잡힌다.
        # → hwpx_fill 과 같은 기준(_inline_texts: 표를 품은 run 제외)으로 본다.
        hits = [p for p in root.iter(_q("p"))
                if anchor and anchor in "".join(
                    t.text or "" for t in _inline_texts(p))]
        if len(hits) != 1:
            report["skipped"].append(f"앵커 {len(hits)}건: {anchor[:40]}")
            continue

        image_id = f"image{next_id}"
        next_id += 1
        href = f"BinData/{image_id}{path.suffix.lower()}"
        added_entries.append((href, path.read_bytes()))
        media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        hpf = hpf.replace(
            "</opf:manifest>",
            f'<opf:item id="{image_id}" href="{href}" '
            f'media-type="{media}" isEmbeded="1"/></opf:manifest>')

        pic = build_picture_element(
            donor, image_id=image_id, px=_px_size(path),
            width_mm=float(spec.get("width_mm", 150)),
            comment=spec.get("comment", ""))

        target = hits[0]
        if spec.get("into_next"):
            nxt = target.getnext()
            if nxt is not None and _local(getattr(nxt, "tag", "")) == "p":
                target = nxt
        run = etree.SubElement(target, _q("run"))
        run.set("charPrIDRef", "0")
        run.append(pic)
        _strip_linesegarray(target, only_under=[target])
        report["added"].append(f"{path.name} → {anchor[:30]} ({image_id})")

    if not report["added"]:
        raise ValueError("추가된 그림이 없습니다 — 앵커를 확인하세요.")

    data[sec_name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                                    standalone=True)
    data[hpf_name] = hpf.encode("utf-8")

    fd, tmp = tempfile.mkstemp(suffix=".hwpx", dir=str(dst.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, data["mimetype"])
            for i in infos:
                if i.filename != "mimetype":
                    zout.writestr(i, data[i.filename])
            for href, blob in added_entries:
                zout.writestr(href, blob)
        shutil.move(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    report["output"] = str(dst)
    return report


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


def picture_display_wh(pic) -> tuple[int, int]:
    """표시 크기(sz, 없으면 curSz)의 가로·세로. 둘 다 >0 이어야 한다(L001/L142)."""
    el = _find_child(pic, "sz")
    if el is None:
        el = _find_child(pic, "curSz")
    if el is None:
        raise ValueError("pic 에 sz/curSz 없음")
    w = int(el.get("width") or 0)
    h = int(el.get("height") or 0)
    if w <= 0 or h <= 0:
        raise ValueError(f"표시 크기 가로·세로가 모두 필요: {w}x{h}")
    return w, h


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

    # 세로는 **지금 화면에 보이는 비율(sz)** 을 유지한다.
    # orgSz 가 실제 그림 비율과 어긋난 양식이 있어(실측: 서명 orgSz 80.4x4.3mm,
    # 표시 5.7x4.5mm), orgSz 비율로 계산하면 그림이 납작하게 눌린다.
    cur = _find_child(pic, "sz")          # `or` 금지 — 자식 없는 요소는 falsy(lxml)
    if cur is None:
        cur = _find_child(pic, "curSz")
    cur_w = int(cur.get("width") or 0) if cur is not None else 0
    cur_h = int(cur.get("height") or 0) if cur is not None else 0

    disp_w = int(round(org_w * scale))
    disp_h = (int(round(disp_w * cur_h / cur_w)) if cur_w > 0 and cur_h > 0
              else int(round(org_h * scale)))
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
    # e1..e6: sx 0 0 0 sy 0 — 가로/세로 배율을 각각 계산(표시 비율 보존과 일치).
    sx = disp_w / org_w if org_w else scale
    sy = disp_h / org_h if org_h else sx
    attrs = ("e1", "e2", "e3", "e4", "e5", "e6")
    vals = (f"{sx:.6f}", "0", "0", "0", f"{sy:.6f}", "0")
    for a, v in zip(attrs, vals):
        sca.set(a, v)

    # 불변 확인
    if org.get("width") != org_before["width"] or org.get("height") != org_before["height"]:
        raise RuntimeError("L088 위반: orgSz 가 변경됨")
    if rect is not None and rect_before is not None:
        for k, v in rect_before.items():
            if rect.get(k) != v:
                raise RuntimeError(f"L088 위반: imgRect.{k} 가 변경됨")

    disp_w, disp_h = picture_display_wh(pic)
    return {
        "scale": scale,
        "org_w": org_w,
        "org_h": org_h,
        "disp_w": disp_w,
        "disp_h": disp_h,
        "orgSz_preserved": True,
        "imgRect_preserved": rect is None or True,
    }
