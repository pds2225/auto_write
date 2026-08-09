# finalizer.py — Single-point finalization control
"""Finalizer — 단일 FINAL/DRAFT 판정 지점.

모든 제출 파일의 최종 명명 권한을 한 곳으로 수렴한다.
LRule report의 can_finalize가 False이면 _DRAFT를 유지한다.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .lrule_enforcer import LRuleReport, STATUS_FAIL, STATUS_REVIEW, STATUS_UNVERIFIABLE

__all__ = [
    "FinalizerResult",
    "Finalizer",
    "finalize_artifact",
]

_DRAFT_TOKENS = ("_DRAFT",)


@dataclass
class FinalizerResult:
    """Finalizer 판정 결과."""
    success: bool = False
    final_path: str = ""
    is_draft: bool = True
    submittable: bool = False
    blocked_reason: str = ""
    lrule_summary: dict = field(default_factory=dict)
    artifact_sha256: str = ""

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "final_path": self.final_path,
            "is_draft": self.is_draft,
            "submittable": self.submittable,
            "blocked_reason": self.blocked_reason,
            "lrule_summary": self.lrule_summary,
            "artifact_sha256": self.artifact_sha256,
        }


class Finalizer:
    """단일 FINAL/DRAFT 판정기."""

    def __init__(self, settings: Any = None):
        self._settings = settings

    def finalize(
        self,
        artifact_path: str | Path,
        lrule_report: LRuleReport,
        output_path: str | Path = None,
        force_draft: bool = False,
    ) -> FinalizerResult:
        """Artifact를 FINAL 또는 DRAFT로 판정한다.

        조건:
        - FAIL = 0
        - REVIEW_REQUIRED = 0
        - UNVERIFIABLE = 0
        - artifact hash 일치
        - registry hash 일치

        불충족 시:
        - _DRAFT 유지
        - submittable = False
        - exit non-zero
        """
        artifact = Path(artifact_path)
        result = FinalizerResult()

        # Compute artifact SHA256
        if artifact.exists():
            result.artifact_sha256 = self._sha256(artifact)

        # Check LRule report
        summary = lrule_report.summary
        result.lrule_summary = summary

        # Force draft if requested
        if force_draft:
            result.is_draft = True
            result.submittable = False
            result.blocked_reason = "forced draft"
            result.final_path = str(self._ensure_draft_name(artifact))
            return result

        # Check finalization conditions
        can_finalize = True
        reasons = []

        if summary.get("fail", 0) > 0:
            can_finalize = False
            reasons.append(f"{summary['fail']} FAIL")

        if summary.get("review_required", 0) > 0:
            can_finalize = False
            reasons.append(f"{summary['review_required']} REVIEW_REQUIRED")

        if summary.get("unverifiable", 0) > 0:
            can_finalize = False
            reasons.append(f"{summary['unverifiable']} UNVERIFIABLE")

        # Artifact hash verification
        if lrule_report.artifact_sha256 and result.artifact_sha256:
            if lrule_report.artifact_sha256 != result.artifact_sha256:
                can_finalize = False
                reasons.append("artifact SHA256 mismatch")

        if not lrule_report.can_finalize:
            can_finalize = False
            if lrule_report.finalization_blocked_reason:
                reasons.append(lrule_report.finalization_blocked_reason)

        if can_finalize:
            # SUCCESS — produce FINAL
            result.success = True
            result.is_draft = False
            result.submittable = True
            if output_path:
                final = Path(output_path)
            else:
                final = self._remove_draft_suffix(artifact)
            result.final_path = str(final)
        else:
            # BLOCKED — keep DRAFT
            result.success = False
            result.is_draft = True
            result.submittable = False
            result.blocked_reason = "; ".join(reasons)
            result.final_path = str(self._ensure_draft_name(artifact))

        return result

    def _sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _ensure_draft_name(self, path: Path) -> Path:
        if path.stem.endswith(_DRAFT_TOKENS):
            return path
        return path.with_name(f"{path.stem}_DRAFT{path.suffix}")

    def _remove_draft_suffix(self, path: Path) -> Path:
        stem = path.stem
        for token in _DRAFT_TOKENS:
            if stem.endswith(token):
                stem = stem[: -len(token)]
                break
        return path.with_name(f"{stem}{path.suffix}")


def finalize_artifact(
    artifact_path: str | Path,
    lrule_report: LRuleReport,
    output_path: str | Path = None,
    force_draft: bool = False,
    settings: Any = None,
) -> FinalizerResult:
    """편의 함수 — artifact를 finalize한다."""
    finalizer = Finalizer(settings)
    return finalizer.finalize(
        artifact_path=artifact_path,
        lrule_report=lrule_report,
        output_path=output_path,
        force_draft=force_draft,
    )
