# -*- coding: utf-8 -*-
"""F6 앞단 레이아웃 방어 — 본문이 길어져도 한글 렌더가 문서 순서를 뒤집지 않게 한다(양식 공통).

실양식(마포 참가신청서) 실환경 검증에서 확인한 두 가지 원인을 일반 규칙으로 막는다.

1. 한 문단에 '떠 있는 표(treatAsChar=0)'가 둘 이상 앵커되어 있으면, 앞 표가 길어졌을 때 한글이
   뒤 표를 다음 문단들 뒤로 밀어낸다(본문 표가 서약서 문장 뒤에 그려짐). 표마다 문단을 하나씩
   갖게 나눈다. 문서 순서·표 내용·속성은 그대로이고 문단 껍데기만 늘어난다.
2. 원본 양식은 부(部)별 제목(사업계획서·서약서·동의서 등)이 새 쪽에서 시작하는데, 본문이 길어지면
   제목이 앞 쪽 중간에서 시작해 한 부가 쪽 사이에 갈라진다. 원본 양식을 한글로 렌더한 PDF 에서
   '쪽 맨 위에서 시작하는 짧은 제목 문단'을 찾아 같은 문단에 쪽 나눔(pageBreak)을 건다.
   원본에서 이미 새 쪽에서 시작하던 문단만 대상이므로 원본의 모양을 바꾸지 않는다.

값·라벨 글자는 건드리지 않는다. 원본 파일은 읽기만 한다.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Sequence

from core.docx.services.hwpx_fill import _local

from .hwpx_xml import assert_not_same, parse_xml, read_hwpx, section_names, serialize_xml, write_hwpx
from .status import Finding, Status

_WS = re.compile(r"\s+")
_TITLE_MIN, _TITLE_MAX = 2, 60  # 쪽 시작 제목 후보의 정규화 글자 수 범위


def _norm(text: str) -> str:
    return _WS.sub("", text or "")


def _full_text(p) -> str:
    return _norm("".join(p.itertext()))


def _floating_table_run(run) -> bool:
    """run 이 '글자처럼 취급하지 않는(treatAsChar=0) 표'를 직접 갖는가."""
    for child in run:
        if _local(child.tag) != "tbl":
            continue
        pos = next((c for c in child if _local(c.tag) == "pos"), None)
        if pos is not None and pos.get("treatAsChar") in ("0", "false"):
            return True
    return False


def split_floating_tables(root) -> int:
    """섹션 루트 직계 문단에 떠 있는 표가 둘 이상이면 2번째 표부터 새 문단으로 옮긴다. 반환: 분리한 표 수."""
    moved = 0
    for p in list(root):
        if _local(p.tag) != "p":
            continue
        runs = [r for r in p if _local(r.tag) == "run"]
        tbl_runs = [r for r in runs if _floating_table_run(r)]
        if len(tbl_runs) < 2:
            continue
        tail_text = [r for r in runs if not any(_local(c.tag) == "tbl" for c in r)
                     and any(_local(c.tag) == "t" for c in r)]
        prev = p
        for run in tbl_runs[1:]:
            new_p = p.makeelement(p.tag, dict(p.attrib))
            p.remove(run)
            new_p.append(run)
            if tail_text:  # 원래 문단 끝의 빈 글자 run 을 복제해 문단 모양을 같게 유지
                new_p.append(copy.deepcopy(tail_text[-1]))
            prev.addnext(new_p)
            prev = new_p
            moved += 1
        for seg in [c for c in p if _local(c.tag) == "linesegarray"]:  # 줄 위치 캐시는 한글이 다시 계산
            p.remove(seg)
    return moved


def baseline_page_start_titles(baseline_hwpx, baseline_pdf) -> list[str]:
    """원본 양식 렌더 PDF 에서 '쪽 맨 위에서 시작하는 짧은 제목 문단'의 정규화 글자 목록(문서 순)."""
    import fitz

    _infos, data = read_hwpx(baseline_hwpx)
    cands: list[str] = []
    for name in section_names(data):
        root = parse_xml(data[name])
        for p in root:
            if _local(p.tag) != "p":
                continue
            text = _full_text(p)
            cands.append(text if _TITLE_MIN <= len(text) <= _TITLE_MAX else "")
    firsts: list[str] = []
    with fitz.open(str(baseline_pdf)) as doc:
        for idx, page in enumerate(doc):
            if idx == 0:
                continue
            lines = []
            for block in page.get_text("dict")["blocks"]:
                for ln in block.get("lines", []):
                    text = "".join(sp["text"] for sp in ln["spans"]).strip()
                    if text:
                        lines.append((round(ln["bbox"][1], 1), ln["bbox"][0], _norm(text)))
            if lines:
                firsts.append(min(lines)[2])
    titles: list[str] = []
    cursor = 0
    for first in firsts:
        if len(first) < 3:
            continue
        for i in range(cursor, len(cands)):
            cand = cands[i]
            if len(cand) >= 3 and (cand == first or cand.startswith(first) or first.startswith(cand)):
                titles.append(cand)
                cursor = i + 1
                break
    return titles


def apply_page_starts(root, titles: Sequence[str]) -> int:
    """제목 목록과 글자가 같은 섹션 직계 문단에 쪽 나눔을 건다. 반환: 새로 건 수."""
    want = {t for t in titles if t}
    n = 0
    for p in root:
        if _local(p.tag) != "p" or p.get("pageBreak") == "1":
            continue
        if _full_text(p) in want:
            p.set("pageBreak", "1")
            n += 1
    return n


def repair_layout(in_hwpx, out_hwpx, *, page_start_titles: Sequence[str] = ()) -> dict[str, Any]:
    """떠 있는 표 분리 + 원본 쪽 시작 제목 고정을 적용해 out_hwpx 로 저장한다(원본 미수정)."""
    assert_not_same(in_hwpx, out_hwpx)
    infos, data = read_hwpx(in_hwpx)
    split = breaks = 0
    for name in section_names(data):
        root = parse_xml(data[name])
        s = split_floating_tables(root)
        b = apply_page_starts(root, page_start_titles)
        if s or b:
            data[name] = serialize_xml(root, data[name])
        split += s
        breaks += b
    write_hwpx(infos, data, out_hwpx)
    findings: list[Finding] = []
    if split:
        findings.append(Finding(
            "LAYOUT_SPLIT_FLOATING", Status.PASS,
            f"자동 검사 PASS: 한 문단에 겹쳐 있던 떠 있는 표 {split}개를 문단별로 분리(본문이 길어져도 순서 유지)",
            source="engine", meta={"split": split}))
    if breaks:
        findings.append(Finding(
            "LAYOUT_PAGE_START", Status.PASS,
            f"자동 검사 PASS: 원본 양식에서 새 쪽에서 시작하던 제목 {breaks}곳에 쪽 나눔 고정",
            source="engine", meta={"page_breaks": breaks}))
    return {"output": str(out_hwpx), "split": split, "page_breaks": breaks, "findings": findings}


# ─────────────── 쪽 넘침 보정: 빈 문단(spacer) 제거 ───────────────
# 값이 길어져 한 부(部)의 마지막 줄 몇 개가 다음 쪽으로 넘어가 거의 빈 쪽이 생길 때, 원본이 줄 간격 용도로 둔
# '빈 문단'을 한 개씩 줄여 본다. 글자·표·그림은 건드리지 않으므로 내용은 그대로이고 간격만 줄어든다.

_SPARSE_RATIO = 0.35     # 마지막 쪽의 내용 하단이 쪽 높이의 이 비율보다 위면 '희박한 쪽'(넘침 꼬리)으로 본다
_OBJECT_TAGS = {"tbl", "pic", "ctrl", "equation", "container", "ole", "rect", "ellipse", "line", "polygon",
                "curve", "arc", "textart", "video", "chart", "switch"}


def _is_blank_spacer(p) -> bool:
    if _local(p.tag) != "p" or p.get("pageBreak") == "1" or p.get("columnBreak") == "1":
        return False
    if _full_text(p):
        return False
    for el in p.iter():
        if el is not p and _local(el.tag) in _OBJECT_TAGS:
            return False
    return True


def section_anchor_texts(root) -> list[str]:
    """섹션 직계 문단 중 쪽 나눔(pageBreak=1)이 걸린 문단의 정규화 글자(문서 순, 첫 문단 제외)."""
    out = []
    for i, p in enumerate(root):
        if i and _local(p.tag) == "p" and p.get("pageBreak") == "1":
            out.append(_full_text(p))
    return out


def _page_fill_ratio(page) -> float:
    bottom = 0.0
    for block in page.get_text("dict")["blocks"]:
        bottom = max(bottom, block["bbox"][3])
    return bottom / page.rect.height if page.rect.height else 1.0


def section_spans(pdf, anchors: Sequence[str]) -> list[tuple[int, int, float]] | None:
    """각 부(0=첫 앵커 앞, k=앵커 k)의 (첫 쪽, 마지막 쪽, 마지막 쪽 내용 하단 비율). 쪽은 1부터.

    앵커를 PDF 에서 못 찾으면 None(판정 불가)."""
    import fitz

    with fitz.open(str(pdf)) as doc:
        firsts: list[str] = []
        ratios: list[float] = []
        for page in doc:
            lines = []
            for block in page.get_text("dict")["blocks"]:
                for ln in block.get("lines", []):
                    text = "".join(sp["text"] for sp in ln["spans"]).strip()
                    if text:
                        lines.append((round(ln["bbox"][1], 1), ln["bbox"][0], _norm(text)))
            firsts.append(min(lines)[2] if lines else "")
            ratios.append(_page_fill_ratio(page))
    starts = [1]
    cursor = 1  # 0 기반 쪽 인덱스 탐색 시작점
    for anchor in anchors:
        hit = next((i for i in range(cursor, len(firsts))
                    if firsts[i] and (firsts[i] == anchor or anchor.startswith(firsts[i]) or firsts[i].startswith(anchor))),
                   None)
        if hit is None:
            return None
        starts.append(hit + 1)
        cursor = hit + 1
    starts.append(len(firsts) + 1)
    return [(starts[k], starts[k + 1] - 1, ratios[starts[k + 1] - 2]) for k in range(len(starts) - 1)]


def find_overflow_sections(final_spans, baseline_spans) -> list[int]:
    """원본보다 쪽이 늘었고 마지막 쪽이 희박한 부(= 값이 길어 몇 줄이 넘어간 부)의 번호."""
    if not final_spans or not baseline_spans or len(final_spans) != len(baseline_spans):
        return []
    out = []
    for k, ((f0, f1, ratio), (b0, b1, _r)) in enumerate(zip(final_spans, baseline_spans)):
        if (f1 - f0) > (b1 - b0) and ratio < _SPARSE_RATIO:
            out.append(k)
    return out


def remove_one_spacer(root, section_index: int) -> bool:
    """section_index 번째 부(앵커 기준)의 마지막 빈 문단 하나를 제거한다. 없으면 False."""
    paragraphs = [p for p in root if _local(p.tag) == "p"]
    bounds = [0] + [i for i, p in enumerate(paragraphs) if i and p.get("pageBreak") == "1"] + [len(paragraphs)]
    if section_index + 1 >= len(bounds):
        return False
    start, end = bounds[section_index], bounds[section_index + 1]
    for p in reversed(paragraphs[start:end]):
        if _is_blank_spacer(p):
            root.remove(p)
            return True
    return False


def compact_overflow(in_hwpx, out_hwpx, section_index: int) -> dict[str, Any]:
    """section_index 부에서 빈 문단 하나를 지워 out_hwpx 로 저장한다. 반환 removed: 지웠는지."""
    assert_not_same(in_hwpx, out_hwpx)
    infos, data = read_hwpx(in_hwpx)
    removed = False
    for name in section_names(data)[:1] if len(section_names(data)) == 1 else []:  # 다중 섹션은 판정 불가
        root = parse_xml(data[name])
        if remove_one_spacer(root, section_index):
            data[name] = serialize_xml(root, data[name])
            removed = True
            break
    write_hwpx(infos, data, out_hwpx)
    return {"output": str(out_hwpx), "removed": removed}


def anchors_of(hwpx) -> list[str]:
    _infos, data = read_hwpx(hwpx)
    out: list[str] = []
    for name in section_names(data):
        out.extend(section_anchor_texts(parse_xml(data[name])))
    return out
