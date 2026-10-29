# -*- coding: utf-8 -*-
"""AW-009 current-대목차 HWPX fill using existing exact/guidance writers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _normalize(text: str) -> str:
    return re.sub(r"[^가-힣a-z0-9]+", "", str(text).lower())


def _score(target: str, name: str) -> float:
    if not target or not name:
        return 0.0
    score = SequenceMatcher(None, target, name).ratio()
    if target == name:
        return 1.0
    if min(len(target), len(name)) >= 5 and (target in name or name in target):
        return max(score, 0.9)
    return score


@dataclass(frozen=True)
class HwpxPartMatch:
    field_label: str
    kind: str  # guidance_narrative | guidance_value
    score: float


@dataclass
class HwpxPartFillResult:
    ok: bool
    output: Path | None
    field_label: str = ""
    kind: str = ""
    source_sha256: str = ""
    scope_ok: bool = False
    reason: str = ""
    written: dict[str, str] | None = None


def list_fillable_fields(index) -> list[HwpxPartMatch]:
    """Collect reusable engine targets that can accept a single-field write."""
    from core.docx.services.hwpx_protected_regions import (
        find_guidance_narrative_targets,
        find_guidance_value_targets,
    )

    rows: list[HwpxPartMatch] = []
    for item in find_guidance_narrative_targets(index):
        rows.append(HwpxPartMatch(item.field_label, "guidance_narrative", 0.0))
    for item in find_guidance_value_targets(index):
        rows.append(HwpxPartMatch(item.field_label, "guidance_value", 0.0))
    return rows


def match_section_field(index, section_title: str) -> HwpxPartMatch:
    """Never silently fill a different field when the heading match is uncertain."""
    target = _normalize(section_title)
    kind_rank = {"guidance_narrative": 0, "guidance_value": 1}
    scored: list[HwpxPartMatch] = []
    for row in list_fillable_fields(index):
        score = _score(target, _normalize(row.field_label))
        if score <= 0:
            continue
        scored.append(HwpxPartMatch(row.field_label, row.kind, score))
    # Same normalized label may appear as narrative + value; keep narrative first.
    best_by_label: dict[str, HwpxPartMatch] = {}
    for item in scored:
        key = _normalize(item.field_label)
        prev = best_by_label.get(key)
        if prev is None:
            best_by_label[key] = item
            continue
        prev_rank = kind_rank.get(prev.kind, 9)
        item_rank = kind_rank.get(item.kind, 9)
        if item.score > prev.score or (item.score == prev.score and item_rank < prev_rank):
            best_by_label[key] = item
    candidates = sorted(best_by_label.values(), key=lambda item: item.score, reverse=True)
    if not candidates or candidates[0].score < 0.72:
        raise ValueError(
            "현재 대목차와 HWPX 채움 가능 필드(guidance narrative/value)를 안전하게 매칭할 수 없습니다. "
            "오매칭 방지를 위해 작성 차단."
        )
    rivals = [
        item
        for item in candidates[1:]
        if item.score >= candidates[0].score - 0.03
        and _normalize(item.field_label) != _normalize(candidates[0].field_label)
    ]
    if rivals:
        raise ValueError("대목차에 대응하는 HWPX 필드가 2개 이상입니다. 임의 선택을 금지합니다.")
    return candidates[0]


def build_draft_text(selected_materials: list[dict[str, Any]], user_instruction: str) -> str:
    chunks: list[str] = []
    instruction = str(user_instruction or "").strip()
    if instruction:
        chunks.append(instruction)
    for i, item in enumerate(selected_materials or [], start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        source = str(item.get("source_file") or "재료")
        page = item.get("page")
        loc = f"p.{page}" if page is not None else "페이지 미확인"
        chunks.append(f"[{i}] {source} / {loc}\n{text}")
    draft = "\n\n".join(chunks).strip()
    if not draft:
        raise ValueError("선택한 근거가 없고 생성 지시도 없습니다.")
    return draft


def fill_current_section(
    source_hwpx: str | Path,
    output_hwpx: str | Path,
    *,
    section_title: str,
    draft_text: str,
) -> HwpxPartFillResult:
    """Fill only the matched current-section field; refuse on out-of-scope XML change."""
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    from core.docx.services.hwpx_fill import commit_guidance_value_writes, commit_t02_label_writes
    from core.docx.services.hwpx_protected_regions import (
        authorize_guidance_narrative_writes,
        authorize_guidance_value_writes,
    )
    from core.docx.services.hwpx_xml_scope_diff import XmlScopeTarget, compare_hwpx_xml_scope

    src = Path(source_hwpx)
    dst = Path(output_hwpx)
    if not src.is_file():
        return HwpxPartFillResult(False, None, reason="SOURCE_MISSING")
    source_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    index = index_hwpx_structure(src)
    if index.analysis_status != "COMPLETE":
        return HwpxPartFillResult(False, None, source_sha256=source_sha, reason="INDEX_INCOMPLETE")
    match = match_section_field(index, section_title)
    draft = str(draft_text or "").strip()
    if not draft:
        return HwpxPartFillResult(False, None, source_sha256=source_sha, reason="EMPTY_DRAFT")

    dst.parent.mkdir(parents=True, exist_ok=True)
    targets: list[XmlScopeTarget] = []
    written: dict[str, str] = {}

    if match.kind == "guidance_narrative":
        report = commit_t02_label_writes(src, dst, {match.field_label: draft})
        if not report.ok:
            return HwpxPartFillResult(
                False, None, match.field_label, match.kind, source_sha,
                reason=report.reason or "NARRATIVE_WRITE_REFUSED",
            )
        written = {match.field_label: draft}
        for grant in authorize_guidance_narrative_writes(index):
            if grant.field_label != match.field_label:
                continue
            targets.append(
                XmlScopeTarget(
                    grant.section_member,
                    grant.paragraph_index,
                    grant.run_index,
                    grant.text_node_index,
                )
            )
    else:
        grants = [g for g in authorize_guidance_value_writes(index) if g.field_label == match.field_label]
        if not grants:
            return HwpxPartFillResult(
                False, None, match.field_label, match.kind, source_sha,
                reason="VALUE_GRANT_MISSING",
            )
        try:
            written = commit_guidance_value_writes(src, dst, grants, {match.field_label: draft})
        except Exception as exc:  # noqa: BLE001 — surface engine refusal
            return HwpxPartFillResult(
                False, None, match.field_label, match.kind, source_sha,
                reason=f"VALUE_WRITE_REFUSED:{type(exc).__name__}:{exc}",
            )
        # commit_guidance_value_writes already refuses OUTSIDE_CELL_XML_CHANGED.
        if not dst.is_file():
            return HwpxPartFillResult(False, None, match.field_label, match.kind, source_sha, reason="NO_OUTPUT")
        return HwpxPartFillResult(
            True, dst, match.field_label, match.kind, source_sha,
            scope_ok=True, written=written,
        )

    if not dst.is_file():
        return HwpxPartFillResult(False, None, match.field_label, match.kind, source_sha, reason="NO_OUTPUT")
    if not targets:
        return HwpxPartFillResult(
            False, dst, match.field_label, match.kind, source_sha,
            scope_ok=False, reason="SCOPE_TARGETS_MISSING", written=written,
        )
    diff = compare_hwpx_xml_scope(src, dst, targets, expected_sha256=source_sha)
    return HwpxPartFillResult(
        ok=bool(diff.ok),
        output=dst,
        field_label=match.field_label,
        kind=match.kind,
        source_sha256=source_sha,
        scope_ok=bool(diff.ok),
        reason="" if diff.ok else f"SCOPE:{diff.verdict}",
        written=written,
    )
