"""image_apply.py — 인포그래픽 '제안'을 받아 그림 위치에 NotebookLM 슬라이드 프롬프트를 삽입한다.

``infographic_suggest.suggest_images_ai`` 가 만든 제안을 받아, 각 제안 위치(anchor) 뒤에
**NotebookLM 의 슬라이드 생성 기능에 그대로 붙여넣을 '프롬프트 텍스트 블록'**을 삽입한다.
사용자는 그 프롬프트를 NotebookLM 에 붙여넣어 슬라이드를 생성한 뒤, 안내 블록은 삭제하면 된다.

(이전 버전은 matplotlib(``chart_generator``)로 차트 PNG 를 직접 만들어 삽입했으나,
지금은 차트 직접 생성 대신 NotebookLM 슬라이드 프롬프트 삽입으로 동작한다.
``chart_generator``/``chart_insert`` 모듈 자체는 보존되며 여기서는 사용하지 않는다.)

안전 원칙
---------
- 원본 DOCX 는 절대 덮어쓰지 않는다(``out_docx == in_docx`` 면 ``ValueError``).
- 정부지원사업 문서 특성상 **없는 숫자는 만들지 않는다(날조 0)** — 슬라이드 프롬프트는
  "문서에 실제로 있는 수치만 쓰라" 는 규칙으로 생성된다(infographic_suggest 참고).
- 제안은 Claude(``openai_service`` 가용 시) 또는 키워드 규칙(폴백)으로 만든다.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from docx import Document
from docx.shared import Pt, RGBColor

from .chart_insert import _next_paragraph
from .infographic_suggest import ImageSuggestion, suggest_images_ai

_DIVIDER = "─" * 30


@dataclass
class ImageApplyItem:
    anchor_text: str
    visual_type: str
    action: str            # "notebooklm_prompt"
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
    prompts_inserted: int = 0
    anchors_missing: int = 0
    output_docx: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "prompts_inserted": self.prompts_inserted,
            "anchors_missing": self.anchors_missing,
            "output_docx": self.output_docx,
            "items": [i.as_dict() for i in self.items],
        }


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


def _add_divider(paragraph) -> None:
    run = paragraph.add_run(_DIVIDER)
    run.font.size = Pt(8)
    try:
        run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    except Exception:  # pragma: no cover - 색상 실패는 치명적이지 않음
        pass


def _add_prompt_header(paragraph, sug: ImageSuggestion) -> None:
    run = paragraph.add_run(
        f"📊 [NotebookLM 슬라이드 생성용 프롬프트] · 유형: {sug.visual_type}  "
        f"(슬라이드 생성 후 이 블록은 삭제하세요)"
    )
    run.bold = True
    run.font.size = Pt(9)
    try:
        run.font.color.rgb = RGBColor(0x33, 0x66, 0xCC)
    except Exception:  # pragma: no cover
        pass


def _add_prompt_intro(paragraph) -> None:
    run = paragraph.add_run("↓ 아래 문장을 NotebookLM 슬라이드 생성에 붙여넣으세요")
    run.italic = True
    run.font.size = Pt(9)
    try:
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    except Exception:  # pragma: no cover
        pass


def _add_prompt_text(paragraph, sug: ImageSuggestion) -> None:
    text = sug.slide_prompt or sug.prompt or f"'{sug.visual_type}' 슬라이드를 만들어줘."
    run = paragraph.add_run(text)
    run.font.size = Pt(10)


def _apply_prompt_block(doc: Document, anchor_para, sug: ImageSuggestion) -> None:
    """anchor 뒤(없으면 문서 끝)에 NotebookLM 프롬프트 블록을 삽입한다."""
    callbacks = [
        _add_divider,
        lambda p: _add_prompt_header(p, sug),
        _add_prompt_intro,
        lambda p: _add_prompt_text(p, sug),
        _add_divider,
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
    openai_service: Optional[Any] = None,
) -> ImageApplyReport:
    """인포그래픽 제안 위치에 NotebookLM 슬라이드 생성 프롬프트를 삽입한다.

    Args:
        in_docx: 원본 DOCX(읽기 전용, 덮어쓰지 않음).
        out_docx: 결과 DOCX 경로. **in_docx 와 같으면 ValueError**.
        max_items: 적용할 최대 제안 수(suggest_images_ai 의 max_suggestions).
        placeholder_only: (하위호환용, 동작에는 영향 없음 — 항상 프롬프트 블록을 삽입).
        openai_service: Claude 제안에 사용할 서비스. None/미가용이면 키워드 규칙으로 폴백.

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

    suggestions = suggest_images_ai(
        doc, openai_service=openai_service, max_suggestions=max_items
    ).suggestions

    for sug in suggestions:
        anchor_para = _find_anchor(doc, sug.anchor_text)
        anchor_found = anchor_para is not None

        _apply_prompt_block(doc, anchor_para, sug)
        report.prompts_inserted += 1
        note = "NotebookLM 슬라이드 프롬프트 삽입"
        if not anchor_found:
            report.anchors_missing += 1
            note += " / anchor 미발견(문서 끝에 추가)"

        report.items.append(ImageApplyItem(
            anchor_text=sug.anchor_text,
            visual_type=sug.visual_type,
            action="notebooklm_prompt",
            anchor_found=anchor_found,
            note=note,
        ))

    doc.save(str(out_path))
    return report


def apply_images_docx(
    path: str,
    out_docx: str,
    *,
    max_items: int = 8,
    placeholder_only: bool = False,
    openai_service: Optional[Any] = None,
) -> ImageApplyReport:
    return apply_images(
        path, out_docx,
        max_items=max_items,
        placeholder_only=placeholder_only,
        openai_service=openai_service,
    )
