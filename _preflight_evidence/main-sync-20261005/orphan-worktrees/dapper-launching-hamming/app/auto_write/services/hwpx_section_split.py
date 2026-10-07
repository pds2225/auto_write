# -*- coding: utf-8 -*-
"""hwpx_section_split — 제출본 분리 시 secPr 첫 문단 재활용(L089) + 선두 쪽나눔 제거(L090).

공고 본문을 떼어 서식만 남길 때 secPr(여백·용지) 든 첫 문단을 지우면
한글이 기본 여백으로 되돌려 표가 잘린다. 첫 문단은 비우고 secPr 만 남긴다.

떼어낸 뒤 남은 첫 문단이 쪽나눔(pageBreak)을 달고 있으면 빈 첫 페이지가 생긴다.
속성을 0 으로 바꾸는 것만으로는 한글이 문서를 열 때 되살리므로(L090),
문단 '구조'를 바꿔서 없앤다 — remove_leading_page_break 참조.
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


def _top_paragraphs(section_root) -> list:
    """섹션 직속 hp:p 만(표 셀 안 문단은 제외)."""
    return [el for el in section_root if _local(getattr(el, "tag", "")) == "p"]


def _page_break_on(p) -> bool:
    return (p.get("pageBreak") or "0").strip().lower() not in ("0", "", "false")


def _para_text(p) -> str:
    return "".join(t.text or "" for t in p.iter(_q("t"))).strip()


def find_page_break_paragraphs(section_root) -> list[int]:
    """쪽나눔이 켜진 섹션 직속 문단의 인덱스 목록."""
    return [i for i, p in enumerate(_top_paragraphs(section_root)) if _page_break_on(p)]


def find_leading_page_break(section_root) -> int:
    """빈 첫 페이지를 만드는 '선두' 쪽나눔 문단의 인덱스. 없으면 -1.

    선두 = 그 앞의 문단들이 모두 글자 없이 비어 있는 경우. 앞에 실제 내용이 있으면
    그 쪽나눔은 의도된 페이지 구분이므로 건드리지 않는다.
    """
    tops = _top_paragraphs(section_root)
    for i, p in enumerate(tops):
        if _page_break_on(p):
            return i if all(not _para_text(q) for q in tops[:i]) else -1
        if _para_text(p):
            return -1
    return -1


def remove_leading_page_break(section_root) -> dict:
    """L090: 빈 첫 페이지를 만드는 선두 쪽나눔을 '문단 구조'로 제거한다.

    pageBreak 속성을 0 으로 바꾸는 것만으로는 안 된다 — 한글이 문서를 열 때
    되살려 빈 페이지가 그대로 남는다(실측 2026-07-27 울산 전문상담위원 신청서).
    그래서 secPr 든 첫 문단(여백 보존용, 삭제 금지 — L089)에 쪽나눔 문단의 서식과
    내용을 옮겨 담고, 쪽나눔을 가진 원래 문단과 그 사이 빈 문단들을 제거한다.

    반환: {ok, removed, donor_index, paragraphs_removed, notes}.
    멱등 — 선두 쪽나눔이 없으면 아무것도 하지 않는다.
    """
    idx = find_leading_page_break(section_root)
    if idx < 0:
        return {"ok": True, "removed": False, "donor_index": -1,
                "paragraphs_removed": 0, "notes": []}

    tops = _top_paragraphs(section_root)
    donor = tops[idx]
    head = find_first_secpr_paragraph(section_root)

    # secPr 문단이 없거나 그것이 곧 쪽나눔 문단이면, 옮겨 담을 그릇이 없다.
    # 이때는 문단을 지우면 여백이 날아가므로(L089) 속성만 끄고 정직하게 보고한다.
    if head is None or head is donor:
        donor.set("pageBreak", "0")
        return {
            "ok": True, "removed": True, "donor_index": idx, "paragraphs_removed": 0,
            "notes": ["secPr 문단이 곧 쪽나눔 문단 — 문단을 지울 수 없어 속성만 껐다. "
                      "한글 왕복 후 빈 페이지가 남는지 반드시 재확인하라(L090)"],
        }
    if head is not tops[0]:
        return {"ok": False, "removed": False, "donor_index": idx,
                "paragraphs_removed": 0,
                "notes": ["secPr 문단이 첫 문단이 아니다 — 자동 처리 중단(양식 확인 필요)"]}

    # secPr 가 run 안에 중첩돼 있어도 안전하게 끌어올려 보존한다(L089 경로 재사용).
    recycle_first_secpr_paragraph(section_root)
    for k in ("paraPrIDRef", "styleIDRef"):
        v = donor.get(k)
        if v is not None:
            head.set(k, v)
    head.set("pageBreak", "0")
    for child in list(donor):
        donor.remove(child)
        head.append(child)

    removed = 0
    for p in tops[1:idx + 1]:
        parent = p.getparent()
        if parent is not None:
            parent.remove(p)
            removed += 1

    return {"ok": True, "removed": True, "donor_index": idx,
            "paragraphs_removed": removed, "notes": []}


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
