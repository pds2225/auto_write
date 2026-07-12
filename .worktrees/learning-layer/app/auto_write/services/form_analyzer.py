"""form_analyzer.py — 제출 '양식(서식)' DOCX/HWP/PDF 를 분석한다.

기존 ``analysis.docx_template.analyze_template`` (+ HWP/PDF 변환 ``document_ingest.ensure_template_docx``)
을 재사용해, 양식에 **무엇을 채워야 하는지**를 사람이 읽기 좋게 요약한다.

  - 작성 항목 수 / 필수 항목 수
  - PSST 4영역(문제·실현·성장·팀) 존재 여부
  - 표 개수(+필수 입력 셀), 이미지 슬롯 수
  - 작성 항목 목록(상위 N), 양식 분석 노트

storage 의존 없이 저수준 함수만 사용한다(읽기 전용 — 원본을 수정하지 않음).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PSST_KEYWORDS = {
    "problem": ("문제인식", "문제 인식", "problem"),
    "solution": ("실현가능성", "실현 가능성", "solution"),
    "scale": ("성장전략", "성장 전략", "scale", "scale-up"),
    "team": ("팀구성", "팀 구성", "team"),
}
_PSST_LABELS = {
    "problem": "Problem(문제인식)",
    "solution": "Solution(실현가능성)",
    "scale": "Scale-up(성장전략)",
    "team": "Team(팀구성)",
}

_NARRATIVE_HINTS = (
    "개요", "계획", "방안", "전략", "목표", "추진", "내용", "설명", "서술",
    "현황", "배경", "필요성", "기대효과", "차별성", "사업화", "로드맵",
    "problem", "solution", "scale", "team", "psst",
)


def classify_field_kind(label: str) -> str:
    """양식 항목이 사실 칸인지 서술 칸인지 분류한다."""
    text = (label or "").strip()
    if not text:
        return "fact"
    lowered = text.lower()
    if any(kw in lowered for kw in _NARRATIVE_HINTS):
        return "narrative"
    if any(kw in text for kws in _PSST_KEYWORDS.values() for kw in kws):
        return "narrative"
    if len(text) >= 24:
        return "narrative"
    return "fact"


@dataclass
class FormReport:
    template_name: str = ""
    source_docx: str = ""
    section_count: int = 0
    table_count: int = 0
    image_slot_count: int = 0
    question_count: int = 0
    required_question_count: int = 0
    required_cell_count: int = 0
    psst_present: dict[str, bool] = field(default_factory=dict)
    writable_items: list[str] = field(default_factory=list)
    writable_item_details: list[dict[str, Any]] = field(default_factory=list)
    analysis_notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "template_name": self.template_name,
            "source_docx": self.source_docx,
            "section_count": self.section_count,
            "table_count": self.table_count,
            "image_slot_count": self.image_slot_count,
            "question_count": self.question_count,
            "required_question_count": self.required_question_count,
            "required_cell_count": self.required_cell_count,
            "psst_present": self.psst_present,
            "psst_missing": [
                _PSST_LABELS[k] for k, v in self.psst_present.items() if not v
            ],
            "writable_items": self.writable_items,
            "writable_item_details": self.writable_item_details,
            "analysis_notes": self.analysis_notes,
        }


def analyze_form(path: str | Path, *, max_items: int = 30) -> FormReport:
    """양식 파일(DOCX/HWP/PDF)을 분석해 작성 항목·구조를 요약한다.

    Args:
        path: 양식 파일 경로.
        max_items: 작성 항목 목록 최대 표시 수.

    Returns:
        FormReport (읽기 전용 — 원본 미수정).
    """
    p = Path(path)
    report = FormReport(template_name=p.name)
    if not p.exists():
        report.analysis_notes.append(f"파일이 없습니다: {p}")
        return report

    # HWP/PDF → DOCX 변환(이미 DOCX 면 그대로), 그 뒤 양식 분석
    try:
        from ..document_ingest import ensure_template_docx

        docx_path, conv_notes = ensure_template_docx(p)
        report.analysis_notes.extend(conv_notes)
    except Exception as exc:
        report.analysis_notes.append(f"양식 변환 실패: {exc}")
        return report

    try:
        from ..analysis.docx_template import analyze_template

        profile = analyze_template(Path(docx_path))
    except Exception as exc:
        report.analysis_notes.append(f"양식 분석 실패: {exc}")
        return report

    report.source_docx = str(docx_path)
    report.section_count = len(profile.sections)
    report.table_count = len(profile.tables)
    report.image_slot_count = len(profile.image_slots)
    report.question_count = len(profile.questions)
    report.required_question_count = sum(1 for q in profile.questions if getattr(q, "required", False))
    report.required_cell_count = sum(
        1
        for t in profile.tables
        for c in getattr(t, "cells", [])
        if getattr(c, "required", False)
    )
    for note in profile.analysis_notes:
        if note not in report.analysis_notes:
            report.analysis_notes.append(note)

    # PSST 영역 존재 여부(질문/섹션 라벨 매칭)
    labels = " ".join(
        [getattr(q, "label", "") for q in profile.questions]
        + [getattr(s, "label", "") for s in profile.sections]
        + [getattr(t, "label", "") for t in profile.tables]
    )
    report.psst_present = {
        k: any(kw in labels for kw in kws) for k, kws in _PSST_KEYWORDS.items()
    }

    # 작성 항목 목록(필수 우선)
    items: list[str] = []
    details: list[dict[str, Any]] = []
    for q in profile.questions:
        label = getattr(q, "label", "").strip()
        if not label:
            continue
        mark = "[필수] " if getattr(q, "required", False) else ""
        items.append(f"{mark}{label}")
        details.append({
            "label": label,
            "field_kind": classify_field_kind(label),
            "required": bool(getattr(q, "required", False)),
        })
    items.sort(key=lambda s: (0 if s.startswith("[필수]") else 1))
    report.writable_items = items[:max_items]
    report.writable_item_details = details[:max_items]

    return report
