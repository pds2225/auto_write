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


_ROW_BUDGET_PT = 240.0     # 한 행 높이 상한 — 행은 쪽 사이에서 나뉘지 않으므로 작게 잘라 제목 표 아래 남는 자리를 채운다
_CHARS_PER_LINE = 42       # 본문 글자 크기 기준 한 줄 글자 수(보수적 추정)
_LINE_PT = 17.6            # 11pt 글자의 줄 간격(160%)


def _para_height_pt(p) -> float:
    """문단 하나가 차지할 높이 추정(pt): 글줄 수 × 줄 간격 + 안에 든 그림 높이."""
    text = "".join(t.text or "" for t in p.iter() if _local(getattr(t, "tag", "")) == "t")
    lines = max(1, -(-len(text) // _CHARS_PER_LINE)) if text else 1
    pics = 0.0
    for pic in p.iter():
        if _local(getattr(pic, "tag", "")) != "pic":
            continue
        for ch in pic:
            if _local(getattr(ch, "tag", "")) == "sz":
                try:
                    pics += int(ch.get("height", "0")) / 100.0
                except ValueError:
                    pass
                break
    return lines * _LINE_PT + pics


def _blank_para(p) -> bool:
    return not _full_text(p) and not any(_local(getattr(x, "tag", "")) in ("pic", "tbl") for x in p.iter())


def _top_level_tables(root) -> list:
    return [t for t in root.iter() if _local(getattr(t, "tag", "")) == "tbl"
            and not any(_local(getattr(a, "tag", "")) == "tbl" for a in t.iterancestors())]


def empty_box_table_indexes(hwpx) -> set[int]:
    """원본 양식에서 '칸 하나 + 글자 있는 줄 2개 이하' 인 빈 서술 상자의 최상위 표 번호(문서 순서, 구역 이어서)."""
    _infos, data = read_hwpx(hwpx)
    out: set[int] = set()
    k = 0
    for name in section_names(data):
        for tbl in _top_level_tables(parse_xml(data[name])):
            cells = [c for c in tbl.iter() if _local(getattr(c, "tag", "")) == "tc"]
            rows = [r for r in tbl if _local(getattr(r, "tag", "")) == "tr"]
            if len(rows) == 1 and len(cells) == 1:
                lines = [_full_text(p) for p in cells[0].iter() if _local(getattr(p, "tag", "")) == "p"]
                if sum(1 for x in lines if x) <= 2:
                    out.add(k)
            k += 1
    return out


def split_long_narrative_cells(root, eligible: set[int] | None = None, start: int = 0) -> int:
    """칸 하나뿐인 서술 상자가 쪽 높이를 넘으면 한글이 칸을 쪽 사이에서 나누지 못해 넘친 글·그림이 잘린다.

    본문 최상위 단일 칸 표 중 추정 높이가 한 쪽 분량을 넘는 표를 문단 경계에서 여러 행으로 나눈다
    (수작업 제출본이 서술 상자를 여러 칸으로 나눈 것과 같은 처리). 문단·그림·글자는 그대로 옮기고
    행 단위만 늘어난다. 칸 끝의 빈 문단 여백은 하나만 남긴다. 반환: 나눈 표 수."""
    n = 0
    for pos, tbl in enumerate(_top_level_tables(root)):
        if eligible is not None and (start + pos) not in eligible:
            continue   # 원본에서 이미 글이 든 칸(동의서 본문 등)은 원래 한 쪽에 들어가므로 건드리지 않는다
        rows = [r for r in tbl if _local(getattr(r, "tag", "")) == "tr"]
        if len(rows) != 1:
            continue
        cells = [c for c in rows[0] if _local(getattr(c, "tag", "")) == "tc"]
        if len(cells) != 1:
            continue
        sub = next((c for c in cells[0] if _local(getattr(c, "tag", "")) == "subList"), None)
        if sub is None:
            continue
        paras = [p for p in sub if _local(getattr(p, "tag", "")) == "p"]
        if any(_local(getattr(x, "tag", "")) == "tbl" for p in paras for x in p.iter()):
            continue
        while len(paras) > 2 and _blank_para(paras[-1]) and _blank_para(paras[-2]):
            sub.remove(paras.pop())
        total = sum(_para_height_pt(p) for p in paras)
        if total <= _ROW_BUDGET_PT * 1.1:
            continue
        chunks: list[list] = [[]]
        used = 0.0
        for p in paras:
            h = _para_height_pt(p)
            if chunks[-1] and used + h > _ROW_BUDGET_PT:
                chunks.append([])
                used = 0.0
            chunks[-1].append(p)
            used += h
        if len(chunks) < 2:
            continue
        template = copy.deepcopy(rows[0])
        heights: list[int] = []
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                row = rows[0]
            else:
                row = copy.deepcopy(template)
                tbl.append(row)
            tc = next(c for c in row if _local(getattr(c, "tag", "")) == "tc")
            tsub = next(c for c in tc if _local(getattr(c, "tag", "")) == "subList")
            for old in [q for q in tsub if _local(getattr(q, "tag", "")) == "p"]:
                tsub.remove(old)
            for q in chunk:
                tsub.append(q)
            height = max(1000, int(sum(_para_height_pt(q) for q in chunk) * 100))   # 행 최소 높이(원본 한 칸 높이를 복사하지 않는다)
            heights.append(height)
            for ch in tc:
                if _local(getattr(ch, "tag", "")) == "cellAddr":
                    ch.set("rowAddr", str(idx))
                elif _local(getattr(ch, "tag", "")) == "cellSz":
                    ch.set("height", str(height))
        tbl.set("rowCnt", str(len(chunks)))
        for ch in tbl:
            if _local(getattr(ch, "tag", "")) == "sz":
                ch.set("height", str(sum(heights)))
            elif _local(getattr(ch, "tag", "")) == "pos" and ch.get("treatAsChar") == "1":
                # 글자처럼 취급된 표는 쪽을 넘으면 뒤가 잘린다 — 수작업 제출본처럼 글자 취급을 풀어 행 단위로 쪽을 넘기게 한다.
                ch.set("treatAsChar", "0")
        n += 1
    return n


def repair_layout(in_hwpx, out_hwpx, *, page_start_titles: Sequence[str] = (),
                  baseline_hwpx=None) -> dict[str, Any]:
    """떠 있는 표 분리 + 원본 쪽 시작 제목 고정을 적용해 out_hwpx 로 저장한다(원본 미수정)."""
    assert_not_same(in_hwpx, out_hwpx)
    infos, data = read_hwpx(in_hwpx)
    split = breaks = cells = 0
    eligible = empty_box_table_indexes(baseline_hwpx) if baseline_hwpx else set()   # 기준 양식이 있어야 서술 상자를 나눈다
    offset = 0
    for name in section_names(data):
        root = parse_xml(data[name])
        s = split_floating_tables(root)
        b = apply_page_starts(root, page_start_titles)
        c = split_long_narrative_cells(root, eligible, offset)
        offset += len(_top_level_tables(root))
        if s or b or c:
            data[name] = serialize_xml(root, data[name])
        split += s
        breaks += b
        cells += c
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
    if cells:
        findings.append(Finding(
            "LAYOUT_CELL_ROWS", Status.PASS,
            f"자동 검사 PASS: 긴 서술 상자 {cells}개를 문단 경계에서 여러 행으로 나눔(쪽을 넘는 글·그림 잘림 방지)",
            source="engine", meta={"cell_rows": cells}))
    return {"output": str(out_hwpx), "split": split, "page_breaks": breaks, "cell_rows": cells, "findings": findings}


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
