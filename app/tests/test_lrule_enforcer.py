# test_lrule_enforcer.py — LRuleEnforcer tests
"""LRuleEnforcer 전수 판정 테스트."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from auto_write.domains.domain_classifier import Domain
from auto_write.services.lrule_enforcer import (
    LRuleEnforcer,
    LRuleReport,
    enforce_lrules,
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_NA,
    STATUS_REVIEW,
    STATUS_UNVERIFIABLE,
)


class TestLRuleEnforcer:
    def test_enforce_bp_domain(self):
        """business_plan 도메인에서 all + bp 규칙은 applicable, ca는 N/A."""
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN)
        assert report.domain == "business_plan"
        assert report.summary["total"] > 100

        # All rules evaluated
        assert report.summary["total"] == report.summary["pass"] + report.summary["na"] + \
               report.summary["fail"] + report.summary["review_required"] + \
               report.summary["unverifiable"] + report.summary["user_override"]

        # BP-specific rules should be applicable
        bp_rules = [r for r in report.rules if r["domain"] == "business_plan"]
        assert all(r["applicable"] for r in bp_rules)

        # CA-specific rules should be N/A
        ca_rules = [r for r in report.rules if r["domain"] == "consultant_application"]
        assert all(r["status"] == "N/A" for r in ca_rules)
        assert all(not r["applicable"] for r in ca_rules)

    def test_enforce_ca_domain(self):
        """consultant_application 도메인에서 ca 규칙은 applicable, bp는 N/A."""
        report = enforce_lrules(domain=Domain.CONSULTANT_APPLICATION)
        assert report.domain == "consultant_application"

        ca_rules = [r for r in report.rules if r["domain"] == "consultant_application"]
        assert all(r["applicable"] for r in ca_rules)

        bp_rules = [r for r in report.rules if r["domain"] == "business_plan"]
        assert all(r["status"] == "N/A" for r in bp_rules)

    def test_enforce_with_guards(self):
        """guard를 제공하면 해당 규칙의 상태가 guard 결과로 결정된다."""
        enforcer = LRuleEnforcer()
        mech = next(l for l in enforcer._lessons if l.get("category") == "mechanized")
        rule_id = mech["id"]
        guards = {rule_id: {"passed": True, "evidence": "test guard passed"}}
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN, guards=guards)
        entry = next(r for r in report.rules if r["id"] == rule_id)
        assert entry["status"] == "PASS"
        assert entry["evidence"] == "test guard passed"

    def test_enforce_with_failing_guard(self):
        """실패한 guard는 FAIL 상태를 만들고 can_finalize를 False로 만든다."""
        enforcer = LRuleEnforcer()
        mech = next(l for l in enforcer._lessons if l.get("category") == "mechanized")
        rule_id = mech["id"]
        guards = {rule_id: {"passed": False, "evidence": "guard failed"}}
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN, guards=guards)
        assert report.summary["fail"] >= 1
        assert not report.can_finalize

    def test_report_has_required_fields(self):
        """report에 필수 필드가 모두 존재해야 한다."""
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN)
        assert report.run_id
        assert report.domain
        assert report.timestamp
        assert report.registry_sha256
        assert report.registry_path
        assert "total" in report.summary
        assert len(report.rules) > 0

    def test_no_missing_rules(self):
        """canonical 규칙이 누락 없이 모두 존재해야 한다."""
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN)
        ids = [r["id"] for r in report.rules]
        # No duplicates
        assert len(ids) == len(set(ids))
        # No missing
        assert report.summary["total"] == len(report.rules)

    def test_report_json_serializable(self):
        """report가 JSON으로 직렬화 가능해야 한다."""
        report = enforce_lrules(domain=Domain.BUSINESS_PLAN)
        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["domain"] == "business_plan"
        assert len(data["rules"]) > 100

    def test_artifact_hash_recorded(self):
        """artifact_path가 있으면 SHA256이 기록되어야 한다."""
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"test content")
            tmppath = f.name
        try:
            report = enforce_lrules(domain=Domain.BUSINESS_PLAN, artifact_path=tmppath)
            assert report.artifact_sha256
            assert len(report.artifact_sha256) == 64  # SHA256 hex
        finally:
            Path(tmppath).unlink()
