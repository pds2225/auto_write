# finalizer.py — Single-point finalization control
"""Finalizer — 단일 FINAL/DRAFT 판정 지점.

모든 제출 파일의 최종 명명 권한을 한 곳으로 수렴한다.
LRule report의 can_finalize가 False이면 _DRAFT를 유지한다.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .lrule_enforcer import (
    ALLOWED_STATUSES,
    LRuleReport,
    STATUS_NA,
    STATUS_REVIEW,
    STATUS_UNVERIFIABLE,
    STATUS_USER_OVERRIDE,
    compute_registry_sha256,
    compute_sha256,
)
from .usage_acceptance import backup_existing_output

__all__ = [
    "FinalizerResult",
    "Finalizer",
    "finalize_artifact",
]

_DRAFT_TOKENS = ("_DRAFT2", "_DRAFT")


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
        materialize: bool = False,
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
            result.artifact_sha256 = compute_sha256(artifact)

        # Check LRule report
        summary = lrule_report.summary
        result.lrule_summary = summary

        # Force draft if requested
        if force_draft:
            result.is_draft = True
            result.submittable = False
            result.blocked_reason = "forced draft"
            draft_path = self._ensure_draft_name(Path(output_path) if output_path else artifact)
            if materialize and artifact.exists() and draft_path != artifact:
                draft_path, error = self._materialize_draft(artifact, draft_path, bool(output_path))
                if error:
                    result.blocked_reason = f"forced draft; {error}"
            result.final_path = str(draft_path)
            return result

        # Check finalization conditions. A report is an attestation over the
        # exact artifact and registry bytes, so both are re-read immediately
        # before any FINAL decision.
        can_finalize = True
        reasons: list[str] = []

        if lrule_report.domain == "other":
            can_finalize = False
            reasons.append("ambiguous or unsupported domain")

        if not artifact.exists():
            can_finalize = False
            reasons.append("artifact does not exist")

        if not lrule_report.artifact_sha256:
            can_finalize = False
            reasons.append("report has no artifact SHA256")
        elif not result.artifact_sha256 or lrule_report.artifact_sha256 != result.artifact_sha256:
            can_finalize = False
            reasons.append("artifact SHA256 mismatch")

        if not lrule_report.registry_path:
            can_finalize = False
            reasons.append("report has no registry path")
        else:
            registry = Path(lrule_report.registry_path)
            if not registry.exists():
                can_finalize = False
                reasons.append("registry does not exist")
            elif not lrule_report.registry_sha256:
                can_finalize = False
                reasons.append("report has no registry SHA256")
            elif compute_registry_sha256(registry) != lrule_report.registry_sha256:
                can_finalize = False
                reasons.append("registry SHA256 mismatch")

        for entry in lrule_report.rules:
            status = entry.get("status")
            evidence = str(entry.get("evidence", "") or "").strip()
            reason = str(entry.get("reason", "") or "").strip()
            if status not in ALLOWED_STATUSES:
                can_finalize = False
                reasons.append(f"unknown rule status: {status}")
            elif status == "PASS" and not evidence:
                can_finalize = False
                reasons.append(f"{entry.get('id', '?')} PASS has no evidence")
            elif status == STATUS_NA and not reason:
                can_finalize = False
                reasons.append(f"{entry.get('id', '?')} N/A has no reason")
            elif status == STATUS_USER_OVERRIDE and (
                not evidence or entry.get("reviewer") != "user"
            ):
                can_finalize = False
                reasons.append(f"{entry.get('id', '?')} USER_OVERRIDE lacks user evidence")

        if summary.get("fail", 0) > 0:
            can_finalize = False
            reasons.append(f"{summary['fail']} FAIL")

        if summary.get("review_required", 0) > 0:
            can_finalize = False
            reasons.append(f"{summary['review_required']} REVIEW_REQUIRED")

        if summary.get("unverifiable", 0) > 0:
            can_finalize = False
            reasons.append(f"{summary['unverifiable']} UNVERIFIABLE")

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
            if materialize and artifact.exists() and final != artifact:
                try:
                    backup_existing_output(final)
                    final.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(artifact, final)
                except OSError as exc:
                    result.success = False
                    result.is_draft = True
                    result.submittable = False
                    result.blocked_reason = f"FINAL materialization failed: {type(exc).__name__}: {exc}"
                    result.final_path = str(artifact)
                    return result
            result.final_path = str(final)
        else:
            # BLOCKED — keep DRAFT
            result.success = False
            result.is_draft = True
            result.submittable = False
            result.blocked_reason = "; ".join(reasons)
            draft_base = Path(output_path) if output_path else artifact
            draft_path = self._ensure_draft_name(draft_base)
            if materialize and artifact.exists() and draft_path != artifact:
                draft_path, error = self._materialize_draft(
                    artifact, draft_path, bool(output_path)
                )
                if error:
                    result.blocked_reason = (
                        f"{result.blocked_reason}; draft materialization failed: {error}"
                    )
            result.final_path = str(draft_path)

        return result

    def _ensure_draft_name(self, path: Path) -> Path:
        if any(path.stem.endswith(token) for token in _DRAFT_TOKENS):
            return path
        return path.with_name(f"{path.stem}_DRAFT{path.suffix}")

    @staticmethod
    def _materialize_draft(path: Path, target: Path, copy_to_target: bool) -> tuple[Path, str]:
        """Materialize the fail-closed decision without duplicating naming policy."""
        try:
            if copy_to_target and target.resolve() != path.resolve():
                backup_existing_output(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                return target, ""
            from .usage_acceptance import force_draft_name

            moved, error = force_draft_name(path)
            if error:
                return path, error
            return moved, ""
        except OSError as exc:
            return path, f"{type(exc).__name__}: {exc}"

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
    materialize: bool = False,
) -> FinalizerResult:
    """편의 함수 — artifact를 finalize한다."""
    finalizer = Finalizer(settings)
    return finalizer.finalize(
        artifact_path=artifact_path,
        lrule_report=lrule_report,
        output_path=output_path,
        force_draft=force_draft,
        materialize=materialize,
    )
