# business_plan/pipeline.py — Domain pipeline facade
"""사업계획서 도메인 파이프라인.

기존 서비스를 호출하는 facade 역할.
실제 구현은 auto_write.services.*에 있고, 이 모듈은 도메인 경계를 제공한다.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

__all__ = ["BusinessPlanPipeline"]


class BusinessPlanPipeline:
    """사업계획서 도메인 파이프라인 facade."""

    def analyze_announcement(self, text: str, **kwargs: Any) -> Any:
        from auto_write.services.announcement_analyzer import analyze_announcement
        return analyze_announcement(text, **kwargs)

    def check_psst(self, doc: Any) -> Any:
        from auto_write.services.psst_check import check_psst
        return check_psst(doc)

    def apply_psst_scaffold(self, doc: Any, report: Any, **kwargs: Any) -> Any:
        from auto_write.services.psst_fill import apply_psst_scaffold
        return apply_psst_scaffold(doc, report, **kwargs)

    def evaluate_plan(self, text: str, criteria: list, **kwargs: Any) -> Any:
        from auto_write.services.evaluation_service import EvaluationService
        svc = EvaluationService()
        return svc.score_plan(text, criteria, **kwargs)

    def run_autopilot(self, docx_path: Path, **kwargs: Any) -> Any:
        from auto_write.services.autopilot_pipeline import run_autopilot
        return run_autopilot(docx_path, **kwargs)

    def run_bizplan_autopilot(self, docx_path: Path, **kwargs: Any) -> Any:
        from auto_write.services.bizplan_autopilot import run_bizplan_autopilot
        return run_bizplan_autopilot(docx_path, **kwargs)
