# test_lrule_domain_gate.py — LRule domain gate tests
"""도메인 인식 L규칙 게이트 테스트."""
from __future__ import annotations

import pytest

from auto_write.domains.domain_classifier import Domain
from auto_write.services.lrule_domain_gate import (
    LRuleDomainGate,
    LRuleJudgment,
    run_domain_aware_lrule_check,
)


class TestLRuleDomainGate:
    def test_domain_distribution(self):
        """L규칙이 3개 도메인으로 분류되어야 한다."""
        gate = LRuleDomainGate.from_coverage_json()
        assert len(gate.lessons) > 100
        domains = {l.get("domain", "all") for l in gate.lessons}
        assert "all" in domains
        assert "business_plan" in domains
        assert "consultant_application" in domains

    def test_bp_rules_na_for_ca(self):
        """business_plan 전용 규칙은 consultant_application에서 N/A여야 한다."""
        gate = LRuleDomainGate.from_coverage_json()
        judgments = gate.check_domain(Domain.CONSULTANT_APPLICATION)
        bp_judgments = [j for j in judgments if j.domain == "business_plan"]
        assert all(j.judgment == "N/A" for j in bp_judgments)

    def test_ca_rules_na_for_bp(self):
        """consultant_application 전용 규칙은 business_plan에서 N/A여야 한다."""
        gate = LRuleDomainGate.from_coverage_json()
        judgments = gate.check_domain(Domain.BUSINESS_PLAN)
        ca_judgments = [j for j in judgments if j.domain == "consultant_application"]
        assert all(j.judgment == "N/A" for j in ca_judgments)

    def test_common_rules_pass_for_both(self):
        """공통 규칙(all)은 모든 도메인에서 PASS여야 한다."""
        gate = LRuleDomainGate.from_coverage_json()
        for domain in [Domain.BUSINESS_PLAN, Domain.CONSULTANT_APPLICATION, Domain.OTHER]:
            judgments = gate.check_domain(domain)
            all_judgments = [j for j in judgments if j.domain == "all"]
            assert all(j.judgment == "PASS" for j in all_judgments)

    def test_run_domain_aware_check_bp(self):
        """사업계획서 텍스트에 대해 BP 도메인 + 해당 규칙이 적용되어야 한다."""
        domain_result, judgments = run_domain_aware_lrule_check(
            text="사업계획서 PSST 창업아이템"
        )
        assert domain_result.domain == Domain.BUSINESS_PLAN
        assert len(judgments) > 100

    def test_run_domain_aware_check_ca(self):
        """이력서 텍스트에 대해 CA 도메인 + 해당 규칙이 적용되어야 한다."""
        domain_result, judgments = run_domain_aware_lrule_check(
            text="이력서 경력 자격 컨설턴트 신청서"
        )
        assert domain_result.domain == Domain.CONSULTANT_APPLICATION
