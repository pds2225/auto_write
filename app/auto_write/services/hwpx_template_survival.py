"""Fail-closed HWPX template survival checks.

This module compares a generated HWPX against the original template without
attempting repair.  It is deliberately conservative: structural content may be
added inside writable regions, but baseline sections/tables/rows/cells/merged
cells/form controls and stable heading/label anchors must not disappear.\n\nGuidance text is intentionally not an anchor because authorized narrative writers\nmay replace a guidance/answer area while preserving its surrounding structure.

The check is generic and contains no project/form-specific strings.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import zipfile
from typing import Any

from lxml import etree

_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_ANCHOR_ROLES = frozenset({"HEADING", "LABEL", "CHOICE_HEADER"})
_FORM_CONTROL_NAMES = frozenset({"checkBtn", "radioBtn", "comboBox", "edit", "listBox", "btn"})


def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _section_key(name: str) -> str:
    match = _SECTION_RE.search(name.replace("\\", "/"))
    return match.group(0).lower() if match else name.lower()


def _section_members(archive: zipfile.ZipFile) -> dict[str, str]:
    return {
        _section_key(name): name
        for name in archive.namelist()
        if _SECTION_RE.search(name.replace("\\", "/"))
    }


def _summary(root) -> dict[str, int]:
    counts = {
        "tables": 0,
        "rows": 0,
        "cells": 0,
        "merged_cells": 0,
        "form_controls": 0,
    }
    for element in root.iter():
        name = _local(getattr(element, "tag", ""))
        if name == "tbl":
            counts["tables"] += 1
        elif name == "tr":
            counts["rows"] += 1
        elif name == "tc":
            counts["cells"] += 1
        elif name == "cellSpan":
            try:
                row_span = int(element.get("rowSpan") or "1")
                col_span = int(element.get("colSpan") or "1")
            except ValueError:
                row_span = col_span = 1
            if row_span > 1 or col_span > 1:
                counts["merged_cells"] += 1
        elif name in _FORM_CONTROL_NAMES:
            counts["form_controls"] += 1
    return counts


def _template_structure(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"올바른 HWPX(ZIP)가 아닙니다: {path.name}")
    sections: dict[str, dict[str, int]] = {}
    with zipfile.ZipFile(path) as archive:
        for key, member in _section_members(archive).items():
            root = etree.fromstring(archive.read(member))
            sections[key] = _summary(root)
    if not sections:
        raise ValueError("Contents/section*.xml 을 찾지 못했습니다")
    return {"sections": sections}


def _normalize_anchor(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _protected_anchors(path: Path) -> Counter[str]:
    """Reuse the existing analyzer to identify text that is not a write target."""
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    from core.docx.services.hwpx_protected_regions import classify_protected_regions

    index = index_hwpx_structure(path)
    report = classify_protected_regions(index)
    anchors: Counter[str] = Counter()
    for decision in report.decisions:
        role = str(getattr(decision, "role", "") or "")
        if role not in _ANCHOR_ROLES:
            continue
        text = _normalize_anchor(getattr(decision, "observed_text", ""))
        if len(text) < 2:
            continue
        anchors[text] += 1
    return anchors


def compare_hwpx_template_survival(
    baseline: str | Path,
    candidate: str | Path,
    *,
    require_protected_anchors: bool = True,
) -> dict[str, Any]:
    """Return a fail-closed comparison of baseline template vs candidate.

    Additions are allowed.  Loss of baseline structure or protected anchors is
    not allowed.  The original and candidate are read-only.
    """
    base = Path(baseline)
    out = Path(candidate)
    base_structure = _template_structure(base)
    out_structure = _template_structure(out)

    defects: list[str] = []
    missing_sections: list[str] = []
    structure_loss: list[dict[str, Any]] = []

    base_sections = base_structure["sections"]
    out_sections = out_structure["sections"]
    for section_key, expected in base_sections.items():
        actual = out_sections.get(section_key)
        if actual is None:
            missing_sections.append(section_key)
            defects.append("SECTION_LOSS")
            continue
        for metric in ("tables", "rows", "cells", "merged_cells", "form_controls"):
            if actual.get(metric, 0) < expected.get(metric, 0):
                structure_loss.append(
                    {
                        "section": section_key,
                        "metric": metric,
                        "baseline": expected.get(metric, 0),
                        "candidate": actual.get(metric, 0),
                    }
                )
    if structure_loss:
        defects.append("STRUCTURAL_LOSS")

    missing_anchors: list[dict[str, Any]] = []
    anchor_counts = {"baseline": 0, "candidate": 0}
    if require_protected_anchors:
        expected_anchors = _protected_anchors(base)
        actual_anchors = _protected_anchors(out)
        anchor_counts = {
            "baseline": sum(expected_anchors.values()),
            "candidate": sum(actual_anchors.values()),
        }
        for text, expected_count in expected_anchors.items():
            actual_count = actual_anchors.get(text, 0)
            if actual_count < expected_count:
                missing_anchors.append(
                    {
                        "text": text[:160],
                        "baseline": expected_count,
                        "candidate": actual_count,
                    }
                )
        if missing_anchors:
            defects.append("PROTECTED_ANCHOR_LOSS")

    defect_codes = list(dict.fromkeys(defects))
    return {
        "ok": not defect_codes,
        "defect_codes": defect_codes,
        "message": (
            "원본 양식 필수 구조·보호 앵커 보존"
            if not defect_codes
            else "원본 양식의 필수 구조 또는 보호 앵커가 손실되었습니다"
        ),
        "baseline": str(base),
        "candidate": str(out),
        "missing_sections": missing_sections,
        "structure_loss": structure_loss[:50],
        "missing_anchors": missing_anchors[:50],
        "anchor_counts": anchor_counts,
        "baseline_structure": base_structure,
        "candidate_structure": out_structure,
    }


__all__ = ["compare_hwpx_template_survival"]
