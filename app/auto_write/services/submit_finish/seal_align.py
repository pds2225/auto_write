# -*- coding: utf-8 -*-
"""F1 보조 — 직인을 '(서명/인)' 표식 위에 겹치도록 렌더 실측 좌표로 맞춘다(L096: 좌표 추측 금지).

기본 삽입(stamp_seals)은 줄 오른쪽 끝에 붙이므로 표식이 줄 가운데에 있으면 도장이 멀리 떨어진다.
1) probe: 모든 직인을 '문단 왼쪽 기준·오프셋 0·줄 세로 가운데'로 바꿔 한 번 렌더한다.
2) align: 렌더 PDF 에서 직인 그림의 x0(= 문단 왼쪽 기준)와 같은 쪽 표식 글자의 가운데 x 를 실측해
   horzOffset 을 계산한다. 표식 글자는 PDF 텍스트 검색으로 찾는다.
부동 개체(treatAsChar=0)라 줄 높이·쪽 수에 영향이 없다. 직인 그림 자체·삽입 개수는 바꾸지 않는다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.docx.services.hwpx_fill import _local

from .hwpx_xml import assert_not_same, paragraph_text_full, parse_xml, read_hwpx, section_names, serialize_xml, write_hwpx
from .seal_stamp import _SEAL_MARKER_RE, _TAG_PREFIX
from .status import Finding, Status

_MATCH_TOL_PT = 2.0


def _seal_pics(root) -> list:
    """AW_SEAL 표식이 있는 pic 요소(문서 순서)."""
    out = []
    for pic in root.iter():
        if _local(getattr(pic, "tag", "")) != "pic":
            continue
        sc = next((c for c in pic if _local(c.tag) == "shapeComment"), None)
        if sc is not None and (sc.text or "").startswith(_TAG_PREFIX):
            out.append(pic)
    return out


def _pic_size_pt(pic) -> tuple[float, float]:
    sz = next((c for c in pic if _local(c.tag) == "sz"), None)
    return int(sz.get("width", 0)) / 100.0, int(sz.get("height", 0)) / 100.0


def _pos(pic):
    return next(c for c in pic if _local(c.tag) == "pos")


def _owner_paragraph(pic):
    el = pic.getparent()
    while el is not None and _local(el.tag) != "p":
        el = el.getparent()
    return el


def make_probe(in_hwpx, out_hwpx) -> dict[str, Any]:
    """직인을 문단 왼쪽 기준·오프셋 0·줄 가운데로 옮긴 probe 사본을 만든다. 반환: seals(개수)."""
    assert_not_same(in_hwpx, out_hwpx)
    infos, data = read_hwpx(in_hwpx)
    n = 0
    for name in section_names(data):
        root = parse_xml(data[name])
        pics = _seal_pics(root)
        for pic in pics:
            pos = _pos(pic)
            pos.set("horzRelTo", "PARA")
            pos.set("horzAlign", "LEFT")
            pos.set("horzOffset", "0")
            pos.set("vertRelTo", "PARA")
            pos.set("vertAlign", "CENTER")
            pos.set("vertOffset", "0")
        if pics:
            data[name] = serialize_xml(root, data[name])
            n += len(pics)
    write_hwpx(infos, data, out_hwpx)
    return {"output": str(out_hwpx), "seals": n}


def align_to_markers(probe_hwpx, probe_pdf, out_hwpx) -> dict[str, Any]:
    """probe 렌더 PDF 로 직인 x 위치를 실측해 표식 가운데에 맞춘 out_hwpx 를 만든다."""
    import fitz

    assert_not_same(probe_hwpx, out_hwpx)
    infos, data = read_hwpx(probe_hwpx)
    roots = {name: parse_xml(data[name]) for name in section_names(data)}
    pics = [(name, pic) for name, root in roots.items() for pic in _seal_pics(root)]
    findings: list[Finding] = []
    aligned = 0
    if not pics:
        write_hwpx(infos, data, out_hwpx)
        return {"output": str(out_hwpx), "aligned": 0, "findings": findings}

    sizes = [_pic_size_pt(p) for _n, p in pics]
    found: list[tuple[int, float, float, float, float]] = []  # (page, x0, y0, x1, y1) 쪽 번호 1~
    with fitz.open(str(probe_pdf)) as doc:
        for pno, page in enumerate(doc, 1):
            for im in page.get_image_info():
                b = im["bbox"]
                w, h = b[2] - b[0], b[3] - b[1]
                if any(abs(w - sw) <= _MATCH_TOL_PT and abs(h - sh) <= _MATCH_TOL_PT for sw, sh in sizes):
                    found.append((pno, b[0], b[1], b[2], b[3]))
        if len(found) != len(pics):
            findings.append(Finding(
                "SEAL_ALIGN_COUNT", Status.REVIEW,
                f"직인 {len(pics)}개 중 렌더에서 {len(found)}개만 식별 — 위치 보정 생략, 사용자 확인 필요",
                source="engine"))
            write_hwpx(infos, data, out_hwpx)
            return {"output": str(out_hwpx), "aligned": 0, "findings": findings}
        found.sort(key=lambda t: (t[0], t[2]))
        for (name, pic), (pno, x0, y0, x1, y1) in zip(pics, found):
            para = _owner_paragraph(pic)
            text = paragraph_text_full(para) if para is not None else ""
            m = _SEAL_MARKER_RE.search(text)
            if m is None:
                continue
            marker = m.group(0)
            page = doc[pno - 1]
            rects = page.search_for(marker) or page.search_for(marker.replace(" ", ""))
            if not rects:
                findings.append(Finding("SEAL_ALIGN_MARKER", Status.REVIEW,
                                        "렌더에서 서명 표식을 찾지 못해 직인 위치 보정 생략 — 사용자 확인 필요",
                                        source="engine", page=pno))
                continue
            cy = (y0 + y1) / 2
            rect = min(rects, key=lambda r: abs((r.y0 + r.y1) / 2 - cy))
            width = x1 - x0
            target_x0 = (rect.x0 + rect.x1) / 2 - width / 2
            delta = target_x0 - x0
            if delta < 0:
                delta = 0.0
            pos = _pos(pic)
            pos.set("horzOffset", str(int(round(delta * 100))))
            aligned += 1
    for name, root in roots.items():
        data[name] = serialize_xml(root, data[name])
    write_hwpx(infos, data, out_hwpx)
    if aligned:
        findings.insert(0, Finding(
            "SEAL_ALIGNED", Status.PASS,
            f"자동 검사 PASS: 직인 {aligned}곳을 서명 표식 위치에 맞춤(렌더 실측), 최종 위치는 사용자 확인 필요",
            source="engine", meta={"aligned": aligned}))
    return {"output": str(out_hwpx), "aligned": aligned, "findings": findings}
