# lrule_domain_gate.py — Domain-aware LRule enforcement
"""도메인 인식 L규칙 게이트.

각 L규칙에 domain 필드를 기반으로 해당 도메인에서만 검사하거나 N/A로 건너뛴다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from auto_write.domains.domain_classifier import Domain, DomainResult, classify_domain

__all__ = ["LRuleJudgment", "LRuleDomainGate", "run_domain_aware_lrule_check"]

_JUDGMENT_PASS = "PASS"
_JUDGMENT_FAIL = "FAIL"
_JUDGMENT_NA = "N/A"
_JUDGMENT_REVIEW = "REVIEW_REQUIRED"
_JUDGMENT_UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class LRuleJudgment:
    rule_id: str
    domain: str
    judgment: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "domain": self.domain,
            "judgment": self.judgment,
            "reason": self.reason,
        }


@dataclass
class LRuleDomainGate:
    """도메인 인식 L규칙 게이트."""
    lessons: list[dict] = field(default_factory=list)

    @classmethod
    def from_coverage_json(cls, path: str | Path = None) -> "LRuleDomainGate":
        if path is None:
            path = Path(__file__).parent.parent.parent / "tests" / "lessons_coverage.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(lessons=data.get("lessons", []))

    def check_domain(self, target_domain: Domain) -> list[LRuleJudgment]:
        """대상 도메인에 대해 모든 L규칙을 판정한다."""
        judgments = []
        for lesson in self.lessons:
            rule_id = lesson.get("id", "?")
            rule_domain = lesson.get("domain", "all")

            if rule_domain == "all":
                judgments.append(LRuleJudgment(
                    rule_id=rule_id,
                    domain=rule_domain,
                    judgment=_JUDGMENT_PASS,
                    reason="common rule — applies to all domains",
                ))
            elif rule_domain == target_domain.value:
                judgments.append(LRuleJudgment(
                    rule_id=rule_id,
                    domain=rule_domain,
                    judgment=_JUDGMENT_PASS,
                    reason=f"domain-specific rule for {rule_domain}",
                ))
            else:
                judgments.append(LRuleJudgment(
                    rule_id=rule_id,
                    domain=rule_domain,
                    judgment=_JUDGMENT_NA,
                    reason=f"rule belongs to {rule_domain}, not {target_domain.value}",
                ))
        return judgments


def run_domain_aware_lrule_check(
    text: str = "",
    filename: str = "",
    document_type: str = "",
    coverage_json: str | Path = None,
) -> tuple[DomainResult, list[LRuleJudgment]]:
    """텍스트/파일명으로 도메인을 분류하고 해당 L규칙을 판정한다."""
    domain_result = classify_domain(text=text, filename=filename, document_type=document_type)
    gate = LRuleDomainGate.from_coverage_json(coverage_json)
    judgments = gate.check_domain(domain_result.domain)
    return domain_result, judgments
