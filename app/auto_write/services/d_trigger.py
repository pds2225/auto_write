"""d_trigger.py — C(칸 채우기) 후 D(서술 작성) 대상 판정.

정책: unmatched_targets ∩ 서술형(writable narrative) 항목만 bizplan 대상.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .form_analyzer import FormReport, analyze_form, classify_field_kind


def _label_of(entry: dict[str, Any]) -> str:
    return str(
        entry.get("target_label")
        or entry.get("normalized")
        or entry.get("label")
        or ""
    ).strip()


def narrative_labels_from_form(form_report: FormReport) -> set[str]:
    """양식 분석에서 서술형으로 분류된 라벨 집합."""
    labels: set[str] = set()
    for detail in form_report.writable_item_details:
        if detail.get("field_kind") == "narrative":
            lab = str(detail.get("label", "")).strip()
            if lab:
                labels.add(lab)
    for raw in form_report.writable_items:
        lab = raw.replace("[필수] ", "").strip()
        if lab and classify_field_kind(lab) == "narrative":
            labels.add(lab)
    return labels


def _labels_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    al, bl = a.lower(), b.lower()
    return al == bl or al in bl or bl in al


def filter_narrative_unmatched(
    unmatched_targets: list[dict[str, Any]],
    form_report: FormReport,
) -> list[dict[str, Any]]:
    """교차 판정 C: 서술형 양식 항목에 해당하는 미매칭만 반환."""
    narr = narrative_labels_from_form(form_report)
    if not narr:
        return []
    out: list[dict[str, Any]] = []
    for entry in unmatched_targets:
        tgt = _label_of(entry)
        if any(_labels_match(tgt, nl) for nl in narr):
            out.append(entry)
    return out


def should_run_bizplan_for_target(
    target_path: str | Path,
    unmatched_targets: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]], FormReport]:
    """대상 양식에 D(bizplan) 를 켤지 판정한다."""
    form_report = analyze_form(target_path)
    gaps = filter_narrative_unmatched(unmatched_targets, form_report)
    return bool(gaps), gaps, form_report
