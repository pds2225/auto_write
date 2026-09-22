# pipeline.py -- resume domain facade
# Canonical: auto_write.domains.consultant_application.pipeline
"""Consultant/resume production finalization.

The resume entry does not decide FINAL itself. It calls the existing pieces:

DomainRouter.resolve_domain → ConsultantApplicationPipeline
→ enforce_lrules → finalize_artifact.
"""
from __future__ import annotations

from pathlib import Path

from auto_write.domains.consultant_application.pipeline import ConsultantApplicationPipeline
from auto_write.domains.domain_classifier import Domain
from auto_write.domains.domain_router import resolve_domain
from auto_write.services.finalizer import FinalizerResult, finalize_artifact
from auto_write.services.lrule_enforcer import LRuleReport, enforce_lrules

__all__ = ["ConsultantApplicationPipeline", "finalize_consultant_resume"]

_BLOCKING_STATUSES = {"FAIL", "REVIEW_REQUIRED", "UNVERIFIABLE"}


def _summary_blocks(report: LRuleReport) -> bool:
    summary = report.summary or {}
    return any(
        summary.get(key, 0)
        for key in ("fail", "review_required", "unverifiable")
    )


def _rule_blocks(report: LRuleReport) -> bool:
    for entry in report.rules or []:
        if entry.get("status") in _BLOCKING_STATUSES:
            return True
    return False


def _decision_blocks(report: LRuleReport, *, pipeline_failed: bool, report_missing: bool) -> bool:
    if pipeline_failed or report_missing:
        return True
    if report.domain == Domain.OTHER.value:
        return True
    if not report.can_finalize:
        return True
    if _summary_blocks(report) or _rule_blocks(report):
        return True
    return False


def _append_reason(report: LRuleReport, reason: str) -> None:
    current = report.finalization_blocked_reason or ""
    if reason in current:
        return
    report.finalization_blocked_reason = f"{current}; {reason}".strip("; ")
    report.can_finalize = False


def _is_draft_name(path: Path) -> bool:
    return path.stem.endswith("_DRAFT") or path.stem.endswith("_DRAFT2")


def _redraft(path: Path, report: LRuleReport) -> FinalizerResult:
    target = path if path.exists() else Path(report.artifact_path) if report.artifact_path else path
    return finalize_artifact(
        artifact_path=target,
        lrule_report=report,
        force_draft=True,
        materialize=True,
    )


def finalize_consultant_resume(
    artifact_path: str | Path,
    *,
    text: str = "",
    filename: str = "",
    document_type: str = "",
    explicit_domain: str = "",
) -> FinalizerResult:
    """Run the consultant/resume production gate on one filled artifact.

    Ambiguous domain (``other``) is not FINAL. A missing LRule report, a
    pipeline failure, or any FAIL / REVIEW_REQUIRED / UNVERIFIABLE status
    is materialized as ``_DRAFT`` and is not submittable.
    """
    artifact = Path(artifact_path)
    try:
        return _finalize_consultant_resume(
            artifact,
            text=text,
            filename=filename,
            document_type=document_type,
            explicit_domain=explicit_domain,
        )
    except Exception as exc:
        report = LRuleReport(
            domain=Domain.OTHER.value,
            document_type=document_type,
            artifact_path=str(artifact),
            can_finalize=False,
            finalization_blocked_reason=f"missing lrule report: {type(exc).__name__}: {exc}",
        )
        try:
            return finalize_artifact(
                artifact_path=artifact,
                lrule_report=report,
                force_draft=True,
                materialize=True,
            )
        except Exception as inner:
            return FinalizerResult(
                success=False,
                final_path=str(artifact),
                is_draft=True,
                submittable=False,
                blocked_reason=(
                    f"missing lrule report: {type(exc).__name__}: {exc}; "
                    f"draft materialization failed: {type(inner).__name__}: {inner}"
                ),
            )


def _finalize_consultant_resume(
    artifact: Path,
    *,
    text: str,
    filename: str,
    document_type: str,
    explicit_domain: str,
) -> FinalizerResult:
    context = resolve_domain(
        text=text,
        filename=filename or artifact.name,
        document_type=document_type,
        explicit_domain=explicit_domain,
    )

    pipeline_failed = False
    try:
        ConsultantApplicationPipeline().check_coverage(artifact)
    except Exception:
        pipeline_failed = True

    report_path = artifact.with_name(f"{artifact.stem}_lrule_report.json")
    report: LRuleReport | None
    try:
        report = enforce_lrules(
            domain=context.domain,
            document_type=document_type,
            artifact_path=artifact,
            report_path=report_path,
            save_report=True,
        )
    except Exception as exc:
        report = None
        pipeline_note = f"missing lrule report: {type(exc).__name__}: {exc}"
    else:
        pipeline_note = ""

    if not isinstance(report, LRuleReport):
        report = LRuleReport(
            domain=context.domain.value,
            document_type=document_type,
            artifact_path=str(artifact),
            can_finalize=False,
            finalization_blocked_reason=pipeline_note or "missing lrule report",
        )

    if pipeline_failed:
        _append_reason(report, "consultant pipeline failed")
    saved = Path(report.report_path) if report.report_path else report_path
    report_missing = not saved.exists()
    if report_missing:
        _append_reason(report, "missing lrule report")

    result = finalize_artifact(
        artifact_path=artifact,
        lrule_report=report,
        materialize=True,
    )
    result = _align_report(result, report, report_path)
    if _needs_redraft(result, report, pipeline_failed=pipeline_failed, report_missing=report_missing):
        redrafted = _redraft(Path(result.final_path) if result.final_path else artifact, report)
        redrafted.blocked_reason = (
            f"{result.blocked_reason}; {redrafted.blocked_reason}".strip("; ")
        )
        result = _align_report(redrafted, report, report_path)
    return result


def _needs_redraft(
    result: FinalizerResult,
    report: LRuleReport,
    *,
    pipeline_failed: bool,
    report_missing: bool,
) -> bool:
    if not _decision_blocks(report, pipeline_failed=pipeline_failed, report_missing=report_missing):
        return False
    final = Path(result.final_path) if result.final_path else Path()
    if result.submittable or not final.exists() or not _is_draft_name(final):
        return True
    return False


def _align_report(
    result: FinalizerResult,
    report: LRuleReport,
    report_path: Path,
) -> FinalizerResult:
    """Point the saved report at the materialized file when the name changed."""
    final_path = Path(result.final_path) if result.final_path else None
    if final_path is None or not final_path.exists():
        return result
    if report.artifact_path == str(final_path):
        return result
    report.artifact_path = str(final_path)
    try:
        report.save(Path(report.report_path) if report.report_path else report_path)
    except Exception as exc:
        result.success = False
        result.is_draft = True
        result.submittable = False
        result.blocked_reason = (
            f"{result.blocked_reason}; missing lrule report: {type(exc).__name__}: {exc}"
        ).strip("; ")
        if not _is_draft_name(final_path):
            return _redraft(final_path, report)
    return result
