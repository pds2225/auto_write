# -*- coding: utf-8 -*-
"""hwpx_section_split — 제출본 분리 시 secPr 첫 문단 재활용(L089).

공고 본문을 떼어 서식만 남길 때 secPr(여백·용지) 든 첫 문단을 지우면
한글이 기본 여백으로 되돌려 표가 잘린다. 첫 문단은 비우고 secPr 만 남긴다.
"""
from __future__ import annotations

from typing import Any, Optional

from .hwpx_fill import _local, _q


def _find_secpr(p) -> Optional[Any]:
    for el in p.iter():
        if _local(getattr(el, "tag", "")) == "secPr":
            return el
    return None


def find_first_secpr_paragraph(section_root):
    """섹션에서 secPr 를 품은 첫 hp:p 를 반환(없으면 None)."""
    for p in section_root.iter(_q("p")):
        if _find_secpr(p) is not None:
            return p
    return None


def recycle_first_secpr_paragraph(section_root) -> dict:
    """L089: secPr 든 첫 문단을 삭제하지 않고 내용만 비워 재활용.

    - secPr 노드(및 그 자손)는 보존
    - 그 문단의 다른 자식(run 등)은 제거
    - secPr 가 없으면 notes 에 기록하고 no-op

    반환: {ok, recycled, had_secpr, page_pr_snapshot, notes}.
    """
    p = find_first_secpr_paragraph(section_root)
    if p is None:
        return {
            "ok": False,
            "recycled": False,
            "had_secpr": False,
            "page_pr_snapshot": {},
            "notes": ["secPr 문단 없음 — 분리 전 양식 확인 필요"],
        }
    secpr = _find_secpr(p)
    snap: dict[str, str] = {}
    if secpr is not None:
        for el in secpr.iter():
            if _local(getattr(el, "tag", "")) == "pagePr":
                for k, v in el.attrib.items():
                    snap[f"pagePr.{k}"] = v
            if _local(getattr(el, "tag", "")) in ("margin", "pageMargin"):
                for k, v in el.attrib.items():
                    snap[f"margin.{k}"] = v

    # secPr 를 문단 직속 자식으로 끌어올리고, 나머지 자식 제거
    if secpr is not None and secpr.getparent() is not p:
        parent = secpr.getparent()
        if parent is not None:
            parent.remove(secpr)
        p.insert(0, secpr)

    for child in list(p):
        if child is not secpr:
            p.remove(child)

    return {
        "ok": True,
        "recycled": True,
        "had_secpr": True,
        "page_pr_snapshot": snap,
        "notes": [],
    }


def assert_pagepr_unchanged(before: dict[str, str], section_root) -> list[str]:
    """왕복 후 pagePr/margin 스냅샷이 같은지 검사. 위반 메시지 목록."""
    p = find_first_secpr_paragraph(section_root)
    if p is None:
        return ["secPr 문단 소실"]
    snap: dict[str, str] = {}
    secpr = _find_secpr(p)
    if secpr is None:
        return ["secPr 소실"]
    for el in secpr.iter():
        if _local(getattr(el, "tag", "")) == "pagePr":
            for k, v in el.attrib.items():
                snap[f"pagePr.{k}"] = v
        if _local(getattr(el, "tag", "")) in ("margin", "pageMargin"):
            for k, v in el.attrib.items():
                snap[f"margin.{k}"] = v
    bad = []
    for k, v in before.items():
        if snap.get(k) != v:
            bad.append(f"{k}: {v!r} → {snap.get(k)!r}")
    return bad
