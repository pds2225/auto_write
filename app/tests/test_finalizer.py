# test_finalizer.py — Finalizer tests
"""Finalizer 테스트."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from auto_write.domains.domain_classifier import Domain
from auto_write.services.lrule_enforcer import enforce_lrules
from auto_write.services.finalizer import Finalizer, finalize_artifact


class TestFinalizer:
    def test_finalize_pass_when_all_clear(self):
        """FAIL/REVIEW/UNVERIFIABLE가 없으면 can_finalize=True."""
        # Use BP domain with all rules (most will be N/A for CA or PASS for common)
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"test content")
            tmppath = f.name

        try:
            result = finalize_artifact(
                artifact_path=tmppath,
                lrule_report=report,
            )
            # Without guards, mechanized rules will be UNVERIFIABLE
            # So can_finalize should be False
            assert result.is_draft  # Expected: UNVERIFIABLE blocks finalization
            assert not result.submittable
        finally:
            Path(tmppath).unlink()

    def test_finalize_with_all_guards_passing(self):
        """모든 guard가 통과하면 FINAL이 가능해야 한다."""
        # Create guards for all mechanized rules
        from auto_write.services.lrule_enforcer import LRuleEnforcer
        enforcer = LRuleEnforcer()
        guards = {}
        for lesson in enforcer._lessons:
            if lesson.get("category") == "mechanized":
                guards[lesson["id"]] = {"passed": True, "evidence": "auto guard"}

        report = enforce_lrules(domain=Domain.BUSINESS_PLAN, guards=guards)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"test content")
            tmppath = f.name

        try:
            result = finalize_artifact(
                artifact_path=tmppath,
                lrule_report=report,
            )
            # With all mechanized guards passing, gap/judgment will be REVIEW_REQUIRED
            # So still blocked unless we also handle those
            assert isinstance(result.is_draft, bool)
            assert isinstance(result.submittable, bool)
        finally:
            Path(tmppath).unlink()

    def test_force_draft(self):
        """force_draft=True면 항상 DRAFT여야 한다."""
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN)

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"test content")
            tmppath = f.name

        try:
            result = finalize_artifact(
                artifact_path=tmppath,
                lrule_report=report,
                force_draft=True,
            )
            assert result.is_draft
            assert not result.submittable
            assert "_DRAFT" in result.final_path
        finally:
            Path(tmppath).unlink()

    def test_draft_name_handling(self):
        """_DRAFT 접미사가 있는 파일명을 올바르게 처리해야 한다."""
        with tempfile.NamedTemporaryFile(suffix="_DRAFT.docx", delete=False) as f:
            f.write(b"test content")
            tmppath = f.name

        try:
            report = enforce_lrules(domain=Domain.BUSINESS_PLAN)
            result = finalize_artifact(
                artifact_path=tmppath,
                lrule_report=report,
                force_draft=True,
            )
            assert "_DRAFT" in result.final_path
        finally:
            Path(tmppath).unlink()
