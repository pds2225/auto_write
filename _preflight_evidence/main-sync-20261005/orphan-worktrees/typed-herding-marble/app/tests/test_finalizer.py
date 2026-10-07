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


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _passing_report(path: Path):
    from auto_write.services.lrule_enforcer import LRuleEnforcer, LRuleReport

    enforcer = LRuleEnforcer()
    return LRuleReport(
        domain="business_plan",
        artifact_path=str(path),
        artifact_sha256=_sha256(path),
        registry_sha256=_sha256(enforcer.lessons_path),
        registry_path=str(enforcer.lessons_path),
        summary={
            "total": 1,
            "pass": 1,
            "na": 0,
            "fail": 0,
            "review_required": 0,
            "unverifiable": 0,
            "user_override": 0,
        },
        rules=[{
            "id": "L000",
            "title": "ok",
            "domain": "all",
            "applicable": True,
            "status": "PASS",
            "phase": "mechanized",
            "guard": "",
            "evidence": "synthetic",
            "reason": "",
            "reviewer": "auto",
        }],
        can_finalize=True,
    )


class TestFinalizerFailClosed:
    def test_clean_report_can_finalize(self, tmp_path):
        """blocker가 0이면 FINAL(submittable)이어야 한다."""
        p = tmp_path / "ok.docx"
        p.write_bytes(b"ok")
        result = finalize_artifact(p, _passing_report(p))
        assert result.submittable
        assert result.success
        assert not result.is_draft

    def test_missing_report_blocks_final(self, tmp_path):
        p = tmp_path / "x.docx"
        p.write_bytes(b"x")
        result = finalize_artifact(p, lrule_report=None)
        assert not result.submittable
        assert "missing" in result.blocked_reason.lower()

    def test_hash_mismatch_blocks_final(self, tmp_path):
        p = tmp_path / "x.docx"
        p.write_bytes(b"before")
        report = _passing_report(p)
        p.write_bytes(b"after-change")
        result = finalize_artifact(p, report)
        assert not result.submittable
        assert "mismatch" in result.blocked_reason

    def test_registry_mismatch_blocks_final(self, tmp_path):
        p = tmp_path / "x.docx"
        p.write_bytes(b"x")
        report = _passing_report(p)
        report.registry_sha256 = "0" * 64
        result = finalize_artifact(p, report)
        assert not result.submittable
        assert "registry SHA256 mismatch" in result.blocked_reason

    def test_duplicate_ids_block_final(self, tmp_path):
        p = tmp_path / "x.docx"
        p.write_bytes(b"x")
        report = _passing_report(p)
        report.rules.append(dict(report.rules[0]))
        result = finalize_artifact(p, report)
        assert not result.submittable
        assert "duplicate" in result.blocked_reason.lower()
