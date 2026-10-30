"""최종 PDF 기술 검사(숫자 판정): 글자 잘림·표 넘침·이미지 이탈/왜곡/중복·빈 쪽·제목 고립·쪽 순서.

AI 시각 검사(visual_qa)와 구분되는 'structural' 출처 결과를 낸다. PyMuPDF 좌표만 사용하므로
토큰·비용이 들지 않는다. 판정은 FAIL/REVIEW 까지만 하며 제출 여부는 판단하지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from .status import Finding, Status

_TOL = 2.0          # pt, 페이지 경계 허용 오차
_ASPECT_TOL = 0.06  # 이미지 표시 비율 vs 원본 픽셀 비율 허용 오차(6%)
_HEADING = re.compile(r"^(\d+\s*[.)]|[가-힣]\s*[.)]|[ⅠⅡⅢⅣⅤ]+\s*[.)])\s*\S")
_TITLE_SIZE_RATIO = 1.1    # 쪽 본문 중앙값 대비 이 배수 이상이면 제목 후보
_TITLE_BLANK_FRAC = 0.15   # 제목 아래 빈 공간이 쪽 높이의 이 비율을 넘으면 본문이 다음 쪽으로 넘어간 것으로 본다
_CLOSING = re.compile(r"(귀하|귀중|드림|올림|제출|\.)$")  # 맺음 줄은 제목이 아니다
_CAPTION = re.compile(r"^[\[\(<]?\s*(그림|표|사진|Figure|Fig\.?|Table)\s*\d+")  # 그림·표 캡션도 제목이 아니다


def _f(code: str, status: Status, msg: str, page: int | None, evidence: str = "") -> Finding:
    return Finding(code=code, status=status, message=msg, source="structural", page=page, evidence=evidence)


def _orphan_title_line(page) -> str:
    """번호 없는 제목(예: '동의서')이 쪽 아래쪽에 홀로 남은 경우 그 줄 글자를 돌려준다. 없으면 ''.

    좌표만 사용한다: 쪽에서 가장 아래 글자 줄이 본문 중앙값보다 충분히 크고 짧으며(맺음 문구 제외),
    그 아래 빈 공간이 쪽 높이의 일정 비율 이상이면 본문이 다음 쪽으로 넘어간 제목으로 본다.
    """
    import statistics

    lines: list[tuple[float, float, str]] = []  # (bottom, size, text)
    for block in page.get_text("dict")["blocks"]:
        for ln in block.get("lines", []):
            text = "".join(sp["text"] for sp in ln["spans"]).strip()
            if text:
                lines.append((ln["bbox"][3], max(sp["size"] for sp in ln["spans"]), text))
    if len(lines) < 3:
        return ""
    median = statistics.median(size for _, size, _ in lines)
    bottom, size, text = max(lines, key=lambda x: x[0])
    if len(text) > 50 or _CLOSING.search(text) or _CAPTION.match(text) or size < median * _TITLE_SIZE_RATIO:
        return ""
    if (page.rect.height - bottom) / page.rect.height <= _TITLE_BLANK_FRAC:
        return ""
    return text


def check_pdf_layout(pdf: str | Path, *, expected_order: Sequence[str] | None = None) -> list[Finding]:
    import fitz

    out: list[Finding] = []
    doc = fitz.open(str(pdf))
    for i, page in enumerate(doc, 1):
        r = page.rect
        words = page.get_text("words")
        # 글자 잘림/표 넘침: 단어 bbox 가 쪽 밖으로 나감
        off = [w for w in words if w[0] < -_TOL or w[1] < -_TOL or w[2] > r.width + _TOL or w[3] > r.height + _TOL]
        if off:
            out.append(_f("PDF_TEXT_OFFPAGE", Status.FAIL, "구조 검사 FAIL: 글자 잘림·표 넘침 의심(쪽 밖 글자)", i, f"{len(off)}개 단어"))
        infos = page.get_image_info(xrefs=True)
        seen: list[tuple] = []
        for im in infos:
            b = fitz.Rect(im["bbox"])
            w, h = im.get("width") or 0, im.get("height") or 0
            if b.width <= 0 or b.height <= 0 or not w or not h:
                continue
            if b.x0 < -_TOL or b.y0 < -_TOL or b.x1 > r.width + _TOL or b.y1 > r.height + _TOL:
                out.append(_f("PDF_IMAGE_OFFPAGE", Status.FAIL, "구조 검사 FAIL: 이미지·직인 위치 이탈", i, f"bbox={tuple(round(v) for v in b)}"))
            shown, native = b.width / b.height, w / h
            if abs(shown - native) / native > _ASPECT_TOL:
                out.append(_f("PDF_IMAGE_DISTORT", Status.FAIL, "구조 검사 FAIL: 이미지 비율 왜곡", i,
                              f"표시 {b.width:.0f}x{b.height:.0f}pt vs 원본 {w}x{h}px"))
            for xref, prev in seen:
                inter = b & prev
                if xref == im.get("xref") and inter.get_area() > 0.9 * min(b.get_area(), prev.get_area()):
                    out.append(_f("PDF_IMAGE_DUP", Status.FAIL, "구조 검사 FAIL: 같은 이미지·직인 중복 겹침", i, ""))
            seen.append((im.get("xref"), b))
        # 비정상 분할 의심: 글자도 이미지도 거의 없는 쪽
        if len(words) < 3 and not infos:
            out.append(_f("PDF_PAGE_EMPTY", Status.REVIEW, "시각적 오류 의심: 거의 빈 쪽(비정상 쪽 나눔 가능) — 사용자 확인 필요", i))
        # 제목만 쪽 끝에 남는 경우
        lines = [ln.strip() for ln in page.get_text("text").splitlines() if ln.strip()]
        if len(lines) >= 3 and len(lines[-1]) <= 40 and _HEADING.match(lines[-1]) and i < len(doc):
            out.append(_f("PDF_ORPHAN_HEADING", Status.REVIEW, "시각적 오류 의심: 쪽 끝에 제목만 남음 — 사용자 확인 필요", i, lines[-1][:30]))
        elif i < len(doc):
            title = _orphan_title_line(page)
            if title:
                out.append(_f("PDF_ORPHAN_HEADING", Status.REVIEW,
                              "시각적 오류 의심: 쪽 아래에 제목만 남고 본문은 다음 쪽으로 넘어감 — 사용자 확인 필요", i, title[:30]))
    if expected_order:
        texts = [p.get_text("text") for p in doc]
        pos: list[int | None] = []
        for key in expected_order:
            pos.append(next((i for i, t in enumerate(texts, 1) if key in t), None))
        missing = [k for k, p in zip(expected_order, pos) if p is None]
        if missing:
            out.append(_f("PDF_ORDER_MISSING", Status.FAIL, "구조 검사 FAIL: 기대한 문서가 합본에 없음(첨부 누락 의심)", None, ", ".join(missing)))
        found = [p for p in pos if p is not None]
        if found != sorted(found):
            out.append(_f("PDF_ORDER_WRONG", Status.FAIL, "구조 검사 FAIL: 합본 쪽 순서가 기대와 다름", None, str(pos)))
    if not out:
        out.append(_f("PDF_LAYOUT", Status.PASS, "자동 검사 PASS: 쪽 밖 글자·이미지 이탈·왜곡·중복·순서 이상 미발견", None))
    return out


# ───────────────────── 읽기 순서(문서 순서 vs PDF 배치) ─────────────────────

_ORDER_PREFIX = 8          # 앵커로 쓰는 글자 수(공백 제거 후 앞부분)
_ORDER_MIN_LEN = 6         # 이보다 짧은 문단은 앵커로 쓰지 않는다(숫자·기호만 있는 칸 등)
_ORDER_Y_TOL = 36.0        # pt, 같은 쪽 안에서 이 이상 거꾸로 가야 순서 이상으로 본다


def _doc_anchors(hwpx) -> list[tuple[str, str]]:
    """HWPX 섹션 직계 블록(문단·표)마다 첫 문단 글자를 (앵커, 원문 앞부분)으로 — 문서 순서.

    블록 안(표 칸 여러 개·여러 줄)의 위아래 순서는 칸 배치 때문에 문서 순서와 달라질 수 있어 비교하지 않고,
    블록 단위 흐름(위에서 아래)만 본다."""
    from core.docx.services.hwpx_fill import _local

    from .hwpx_xml import paragraph_text_full, parse_xml, read_hwpx, section_names

    _infos, data = read_hwpx(hwpx)
    out: list[tuple[str, str]] = []
    for name in section_names(data):
        root = parse_xml(data[name])
        for block in root:
            if _local(getattr(block, "tag", "")) != "p":
                continue
            for p in block.iter():
                if _local(getattr(p, "tag", "")) != "p":
                    continue
                text = re.sub(r"\s+", "", paragraph_text_full(p))
                if len(text) >= _ORDER_MIN_LEN:
                    out.append((text[:_ORDER_PREFIX], text[:20]))
                    break
    return out


def _order_inversions(pdf, hwpx) -> tuple[list[tuple[str, str, str, int, int]], int]:
    """(앞서야 할 앵커 prefix, 실제로 앞에 놓인 앵커 prefix, 표시 문구 2개, 쪽 2개)의 목록과 비교한 앵커 수."""
    import fitz

    anchors = _doc_anchors(hwpx)
    doc = fitz.open(str(pdf))
    lines: list[tuple[int, float, str]] = []  # (page, y0, 공백 제거 줄 글자)
    for pno, page in enumerate(doc, 1):
        for block in page.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                text = re.sub(r"\s+", "", "".join(sp["text"] for sp in ln["spans"]))
                if text:
                    lines.append((pno, ln["bbox"][1], text))
    doc.close()
    counts: dict[str, int] = {}
    for key, _ in anchors:
        counts[key] = counts.get(key, 0) + 1
    placed: list[tuple[str, str, int, float]] = []  # (앵커, 표시 문구, page, y)
    for key, shown in anchors:
        if counts[key] != 1:
            continue
        hits = [(pno, y) for pno, y, text in lines if text.startswith(key)]
        if len(hits) == 1:
            placed.append((key, shown, hits[0][0], hits[0][1]))
    bad: list[tuple[str, str, str, int, int]] = []
    prev = None
    for cur in placed:
        if prev is not None:
            (pk, pt, ppage, py), (ck, ct, cpage, cy) = prev, cur
            if cpage < ppage or (cpage == ppage and cy < py - _ORDER_Y_TOL):
                bad.append((pk, ck, f"'{ct}'(p{cpage}) 가 '{pt}'(p{ppage}) 보다 앞에 배치", ppage, cpage))
                continue  # prev 는 유지해 한 번의 밀림이 연쇄 오보가 되지 않게 한다
        prev = cur
    return bad, len(placed)


def check_reading_order(pdf: str | Path, hwpx: str | Path, *,
                        baseline: tuple[str | Path, str | Path] | None = None) -> list[Finding]:
    """HWPX 블록(문단·표)의 문서 순서가 PDF 의 쪽·세로 배치 순서와 같은지 본다(본문이 엉뚱한 쪽으로 밀리는 사고 검출).

    앵커는 블록 첫 문단 앞 8글자(공백 제거). PDF 와 HWPX 양쪽에서 유일한 앵커만 비교해 오탐을 줄인다.
    같은 쪽에서는 ±36pt 이상 거꾸로 갈 때, 다른 쪽이면 앞선 블록이 더 뒤 쪽에 있을 때 FAIL.
    baseline=(원본 양식 렌더 PDF, 원본 양식 HWPX) 를 주면 원본 양식이 이미 그렇게 배치된 쌍(오른쪽 상자·여백 노트 등)은
    제외하고 '작성하면서 새로 생긴' 순서 이상만 보고한다."""
    bad, compared = _order_inversions(pdf, hwpx)
    if baseline is not None and bad:
        try:
            base_bad, _n = _order_inversions(*baseline)
            known = {(a, b) for a, b, *_ in base_bad}
            bad = [item for item in bad if (item[0], item[1]) not in known]
        except Exception:  # 원본 판독 실패는 비교만 생략한다
            pass
    if bad:
        return [_f("PDF_READING_ORDER", Status.FAIL,
                   "구조 검사 FAIL: 문서 순서와 PDF 배치 순서가 다름(본문이 엉뚱한 쪽·위치로 밀림 의심)", None,
                   "; ".join(item[2] for item in bad[:5]))]
    return [_f("PDF_READING_ORDER", Status.PASS,
               f"자동 검사 PASS: 문서 순서와 PDF 배치 순서 일치(비교 블록 {compared}개)", None)]
