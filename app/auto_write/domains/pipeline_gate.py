# pipeline_gate.py — DomainRouter → LRule → Hash → Finalizer
"""문서 제출 경로의 단일 수렴점.

INPUT → DomainRouter → LRuleEnforcer → artifact/registry SHA256 → Finalizer
→ FINAL 또는 _DRAFT.

기존 CORE 서비스(autopilot / resume fill / 품질 파이프라인)가 산출한
artifact 를 이 게이트로 통과시킨다. 생성 로직을 재구현하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from auto_write.domains.domain_classifier import Domain
from auto_write.domains.domain_router import DomainContext, DomainRouter
from auto_write.services.finalizer import FinalizerResult, finalize_artifact
from auto_write.services.lrule_enforcer import LRuleReport, enforce_lrules

__all__ = ["PipelineGateResult", "run_to_final"]


@dataclass
class PipelineGateResult:
    """도메인 파이프라인 게이트 결과."""

    domain: str = Domain.OTHER.value
    confidence: float = 0.0
    reason: str = ""
    ambiguous: bool = True
    lrule_report: Optional[LRuleReport] = None
    finalizer: Optional[FinalizerResult] = None
    renamed_path: str = ""
    rename_error: str = ""
    blocked_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "ambiguous": self.ambiguous,
            "lrule_summary": self.lrule_report.summary if self.lrule_report else {},
            "lrule_can_finalize": bool(self.lrule_report and self.lrule_report.can_finalize),
            "finalizer": self.finalizer.as_dict() if self.finalizer else {},
            "renamed_path": self.renamed_path,
            "rename_error": self.rename_error,
            "blocked_reason": self.blocked_reason,
            "submittable": bool(self.finalizer and self.finalizer.submittable),
        }


def run_to_final(
    artifact_path: str | Path,
    *,
    explicit_domain: str = "",
    document_type: str = "",
    text: str = "",
    filename: str = "",
    guards: Optional[dict[str, Any]] = None,
    force_draft: bool = False,
    apply_draft_name: bool = True,
    avoid_path: str | Path | None = None,
    settings: Any = None,
) -> PipelineGateResult:
    """DomainRouter → LRule → Hash → Finalizer 를 한 번에 실행한다.

    ambiguous domain / LRule blocker / hash mismatch 이면 FINAL 금지.
    apply_draft_name=True 이면 실제 파일을 ``force_draft_name`` 으로 고친다
    (명명 정책 단일 출처: usage_acceptance).
    """
    artifact = Path(artifact_path)
    result = PipelineGateResult(renamed_path=str(artifact))

    router = DomainRouter(settings)
    if text or filename or explicit_domain or document_type:
        ctx: DomainContext = router.resolve(
            text=text,
            filename=filename or artifact.name,
            document_type=document_type,
            explicit_domain=explicit_domain,
        )
    elif artifact.exists():
        ctx = router.resolve_from_docx(artifact)
    else:
        ctx = router.resolve(
            filename=artifact.name,
            document_type=document_type,
            explicit_domain=explicit_domain,
        )

    result.domain = ctx.domain.value
    result.confidence = ctx.domain_result.confidence
    result.reason = ctx.domain_result.reason
    result.ambiguous = ctx.domain_result.is_ambiguous()

    gate_force = force_draft or result.ambiguous
    if result.ambiguous and not force_draft:
        result.blocked_reason = f"ambiguous domain ({result.domain}, conf={result.confidence:.3f})"

    lrule_report: Optional[LRuleReport] = None
    try:
        lrule_report = enforce_lrules(
            domain=ctx.domain,
            document_type=document_type or ctx.document_type,
            artifact_path=str(artifact) if artifact.exists() else "",
            guards=guards,
        )
        result.lrule_report = lrule_report
    except Exception as exc:  # noqa: BLE001 — 검사불능은 FINAL 금지
        result.blocked_reason = (
            f"{result.blocked_reason}; lrule_error:{type(exc).__name__}: {exc}"
            if result.blocked_reason
            else f"lrule_error:{type(exc).__name__}: {exc}"
        )
        gate_force = True

    finalizer = finalize_artifact(
        artifact_path=str(artifact),
        lrule_report=lrule_report,
        force_draft=gate_force,
        settings=settings,
    )
    if gate_force and result.ambiguous and finalizer.blocked_reason == "forced draft":
        finalizer.blocked_reason = result.blocked_reason or "forced draft"
    result.finalizer = finalizer
    if not result.blocked_reason:
        result.blocked_reason = finalizer.blocked_reason

    if apply_draft_name and not finalizer.submittable and artifact.exists():
        try:
            from auto_write.services.usage_acceptance import force_draft_name

            avoid = Path(avoid_path) if avoid_path else None
            new_path, err = force_draft_name(artifact, avoid=avoid)
            result.renamed_path = str(new_path)
            result.rename_error = err
            finalizer.final_path = str(new_path)
        except Exception as exc:  # noqa: BLE001
            result.rename_error = f"{type(exc).__name__}: {exc}"
    else:
        result.renamed_path = finalizer.final_path or str(artifact)

    return result
