# consultant_application/pipeline.py — Domain pipeline facade
"""컨설턴트 신청서 도메인 파이프라인.

기존 서비스를 호출하는 facade 역할.
실제 구현은 auto_write.services.*에 있고, 이 모듈은 도메인 경계를 제공한다.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

__all__ = ["ConsultantApplicationPipeline"]


class ConsultantApplicationPipeline:
    """컨설턴트 신청서 도메인 파이프라인 facade."""

    def extract_profile(self, paths: list[Path], **kwargs: Any) -> Any:
        from auto_write.services.resume_extract import build_profile
        return build_profile(paths, **kwargs)

    def fill_resume_form(self, hwpx_path: Path, profile: Any, **kwargs: Any) -> Any:
        from auto_write.services.resume_fill_service import fill_resume_form
        return fill_resume_form(hwpx_path, profile, **kwargs)

    def map_form_sections(self, hwpx_path: Path) -> Any:
        from auto_write.services.resume_form_map import map_form_sections
        return map_form_sections(hwpx_path)

    def supplement_resume(self, hwpx_path: Path, facts: list, **kwargs: Any) -> Any:
        from auto_write.services.hwpx_resume_supplement import supplement_hwpx_from_resume
        return supplement_hwpx_from_resume(hwpx_path, facts, **kwargs)

    def check_coverage(self, hwpx_path: Path) -> Any:
        from auto_write.services.hwpx_fill_coverage import score_hwpx_coverage
        return score_hwpx_coverage(hwpx_path)

    def autofill_cross_form(self, source_doc: Any, target_doc: Any, **kwargs: Any) -> Any:
        from auto_write.services.cross_form_autofill import autofill_from_source
        return autofill_from_source(source_doc, target_doc, **kwargs)

    def run_to_final(self, artifact_path: Path, **kwargs: Any) -> Any:
        """DomainRouter → LRule → Hash → Finalizer. 산출물 제출 게이트."""
        from auto_write.domains.pipeline_gate import run_to_final
        kwargs.setdefault("explicit_domain", "consultant_application")
        kwargs.setdefault("document_type", "resume")
        return run_to_final(artifact_path, **kwargs)
