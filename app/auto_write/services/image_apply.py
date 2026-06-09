"""image_apply.py — 인포그래픽 '제안'을 실제로 DOCX 에 '적용(삽입)'한다.

``infographic_suggest.suggest_images`` 가 만든 제안을 받아, 각 제안 위치(anchor)에:

  1) 문서의 **표에서 명확한 (라벨, 숫자) 시계열**이 추출되면
     ``chart_generator`` 로 차트 PNG 를 생성해 실제로 삽입한다(문서 원문 숫자만 사용).
  2) 추출이 불가능하면 **데이터 입력 자리표시(placeholder)** 단락을 삽입한다.
     숫자는 절대 지어내지 않는다(빈칸 유지). 사용자가 직접 데이터를 채우면 된다.

안전 원칙
---------
- 원본 DOCX 는 절대 덮어쓰지 않는다(``out_docx == in_docx`` 면 ``ValueError``).
- 정부지원사업 문서 특성상 **없는 숫자는 만들지 않는다(날조 0)**. 추출 실패 시 placeholder.
- ``chart_generator`` 의 각 함수는 데이터가 유효하지 않으면 ``None`` 을 돌려주므로,
  잘못된 데이터로 만든 차트가 삽입될 일이 없다(이중 안전장치).
"""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from docx import Document
from docx.shared import Pt, RGBColor

from . import chart_generator
from .chart_insert import _add_caption, _add_picture, _next_paragraph
from .infographic_suggest import ImageSuggestion, suggest_images

# 표 셀에서 순수 숫자(콤마/소수/퍼센트)만 보수적으로 파싱
_PURE_NUM_RE = re.compile(r"-?\d+\.?\d*")

# 데이터 시계열을 차트로 그릴 수 있는 visual_type (막대/추세 계열만)
_BARCHARTABLE = {"막대/도넛 차트", "추세 선/막대 그래프"}


@dataclass
class ImageApplyItem:
    anchor_text: str
    visual_type: str
    action: str            # "chart" | "placeholder"
    anchor_found: bool
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "anchor_text": self.anchor_text[:80],
            "visual_type": self.visual_type,
            "action": self.action,
            "anchor_found": self.anchor_found,
            "note": self.note,
        }


@dataclass
class ImageApplyReport:
    items: list[ImageApplyItem] = field(default_factory=list)
    charts_inserted: int = 0
    placeholders_inserted: int = 0
    anchors_missing: int = 0
    output_docx: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "charts_inserted": self.charts_inserted,
            "placeholders_inserted": self.placeholders_inserted,
            "anchors_missing": self.anchors_missing,
            "output_docx": self.output_docx,
            "items": [i.as_dict() for i in self.items],
        }


def _parse_num(text: str) -> Optional[float]:
    """표 셀 텍스트에서 순수 숫자만 파싱한다(콤마·% 허용). 아니면 None."""
    if not text:
        return None
    t = text.replace(",", "").replace("%", "").strip()
    if _PURE_NUM_RE.fullmatch(t):
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _extract_series_from_tables(doc: Document) -> Optional[tuple[list[str], list[float]]]:
    """표에서 (라벨, 숫자) 시계열을 보수적으로 추출한다(없으면 None).

    문서에 실제로 적힌 표 숫자만 사용한다 — 새 숫자를 만들지 않는다.
    가로형(첫 행=라벨, 다른 한 행=값)을 우선 시도한다.
    """
    for table in doc.tables:
        rows = table.rows
        if len(rows) < 2:
            continue
        labels = [c.text.strip() for c in rows[0].cells]
        for r in rows[1:]:
            vals = [_parse_num(c.text.strip()) for c in r.cells]
            num_count = sum(v is not None for v in vals)
            if num_count >= 2:
                pairs = [
                    (lab, val)
                    for lab, val in zip(labels, vals)
                    if val is not None and lab
                ]
                if len(pairs) >= 2:
                    return [p[0] for p in pairs], [p[1] for p in pairs]
    return None


def _add_guide(paragraph, text: str) -> None:
    """자리표시 안내(회색 이탤릭) 단락을 만든다."""
    run = paragraph.add_run(text)
    run.italic = True
    run.font.size = Pt(9)
    try:
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    except Exception:  # pragma: no cover - 색상 실패는 치명적이지 않음
        pass


def _insert_after_anchor(doc: Document, anchor_para, callbacks: list) -> None:
    """anchor 단락 바로 뒤에 callbacks(각각 para 를 받는 함수)를 순서대로 삽입한다."""
    next_para = _next_paragraph(anchor_para)
    if next_para is not None:
        for cb in callbacks:
            p = next_para.insert_paragraph_before()
            cb(p)
    else:
        for cb in callbacks:
            cb(doc.add_paragraph())


def _find_anchor(doc: Document, anchor_text: str):
    if not anchor_text:
        return None
    key = anchor_text[:40]
    if not key:
        return None
    for para in doc.paragraphs:
        if key in para.text:
            return para
    return None


def _apply_chart(doc: Document, anchor_para, png_path: str, sug: ImageSuggestion) -> None:
    callbacks = [lambda p: _add_picture(p, png_path, 6.0)]
    if sug.caption:
        callbacks.append(lambda p: _add_caption(p, sug.caption))
    if anchor_para is not None:
        _insert_after_anchor(doc, anchor_para, callbacks)
    else:
        for cb in callbacks:
            cb(doc.add_paragraph())


def _apply_placeholder(doc: Document, anchor_para, sug: ImageSuggestion) -> None:
    guide = (
        f"└ [{sug.visual_type}] 삽입 권장 자리 — 데이터를 입력하면 차트로 자동 생성됩니다. "
        f"(트리거 키워드: {sug.keyword})"
    )
    callbacks = [
        lambda p: _add_caption(p, sug.caption),
        lambda p: _add_guide(p, guide),
    ]
    if anchor_para is not None:
        _insert_after_anchor(doc, anchor_para, callbacks)
    else:
        for cb in callbacks:
            cb(doc.add_paragraph())


def apply_images(
    in_docx: str,
    out_docx: str,
    *,
    max_items: int = 8,
    placeholder_only: bool = False,
) -> ImageApplyReport:
    """인포그래픽 제안을 실제 DOCX 에 적용(차트 삽입 또는 자리표시 삽입)한다.

    Args:
        in_docx: 원본 DOCX(읽기 전용, 덮어쓰지 않음).
        out_docx: 결과 DOCX 경로. **in_docx 와 같으면 ValueError**.
        max_items: 적용할 최대 제안 수(suggest_images 의 max_suggestions).
        placeholder_only: True 면 차트를 만들지 않고 자리표시만 삽입(가장 안전).

    Returns:
        ImageApplyReport — 삽입 결과 집계.
    """
    in_path = Path(in_docx)
    out_path = Path(out_docx)
    if in_path.resolve() == out_path.resolve():
        raise ValueError("in_docx 와 out_docx 가 같습니다. 원본 덮어쓰기는 금지입니다.")
    if not in_path.exists():
        raise FileNotFoundError(f"입력 DOCX 가 없습니다: {in_docx}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(in_path), str(out_path))

    doc = Document(str(out_path))
    report = ImageApplyReport(output_docx=str(out_path))

    suggestions = suggest_images(doc, max_suggestions=max_items).suggestions
    series = None if placeholder_only else _extract_series_from_tables(doc)

    tmp_dir = Path(tempfile.mkdtemp(prefix="autowrite_charts_"))
    try:
        for idx, sug in enumerate(suggestions):
            anchor_para = _find_anchor(doc, sug.anchor_text)
            anchor_found = anchor_para is not None

            png_path: Optional[str] = None
            if (
                not placeholder_only
                and series is not None
                and sug.visual_type in _BARCHARTABLE
            ):
                png_path = chart_generator.bar_chart(
                    str(tmp_dir / f"chart_{idx}.png"),
                    sug.caption.replace("[그림] ", ""),
                    series[0],
                    series[1],
                )

            if png_path:
                _apply_chart(doc, anchor_para, png_path, sug)
                report.charts_inserted += 1
                action, note = "chart", "표 실측치로 차트 생성"
            else:
                _apply_placeholder(doc, anchor_para, sug)
                report.placeholders_inserted += 1
                action = "placeholder"
                note = "데이터 미추출 → 자리표시(숫자 비움)"

            if not anchor_found:
                report.anchors_missing += 1
                note += " / anchor 미발견(문서 끝에 추가)"

            report.items.append(ImageApplyItem(
                anchor_text=sug.anchor_text,
                visual_type=sug.visual_type,
                action=action,
                anchor_found=anchor_found,
                note=note,
            ))
        doc.save(str(out_path))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return report


def apply_images_docx(
    path: str,
    out_docx: str,
    *,
    max_items: int = 8,
    placeholder_only: bool = False,
) -> ImageApplyReport:
    return apply_images(
        path, out_docx, max_items=max_items, placeholder_only=placeholder_only
    )
