# domain_classifier.py — Domain classification
"""도메인 분류기.

문서 유형과 작업 맥락을 기반으로 business_plan / consultant_application / other 를 판별한다.
기존 document_type_classifier와 호환되며, domain 개념을 상위 레벨로 추가한다.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

__all__ = ["Domain", "DomainResult", "classify_domain"]


class Domain(str, Enum):
    BUSINESS_PLAN = "business_plan"
    CONSULTANT_APPLICATION = "consultant_application"
    OTHER = "other"


# Keyword matches start at 0.7; OTHER is 0.3. Below this is REVIEW_REQUIRED.
_AMBIGUOUS_CONFIDENCE = 0.5


@dataclass
class DomainResult:
    domain: Domain
    confidence: float
    reason: str

    def is_ambiguous(self) -> bool:
        """모호하면 FINAL 금지. OTHER 또는 신뢰도 부족."""
        return self.domain == Domain.OTHER or self.confidence < _AMBIGUOUS_CONFIDENCE

    def as_dict(self) -> dict:
        return {
            "domain": self.domain.value,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "ambiguous": self.is_ambiguous(),
        }


_BUSINESS_PLAN_TYPES = {"business_plan", "rnd_plan", "pitch_deck"}
_CONSULTANT_TYPES = {"application_form", "resume", "pledge", "consent_form"}

_BP_KEYWORDS = {"사업계획서", "PSST", "창업아이템", "사업화", "평가기준", "공고"}
_CA_KEYWORDS = {"이력서", "신청서", "컨설턴트", "경력", "자격", "수행실적", "전문분야"}


def classify_domain(
    text: str = "",
    filename: str = "",
    document_type: str = "",
) -> DomainResult:
    """문서 텍스트/파일명/문서유형을 기반으로 도메인을 분류한다."""
    haystack = f"{filename}\n{text}".lower()

    if document_type:
        if document_type in _BUSINESS_PLAN_TYPES:
            return DomainResult(Domain.BUSINESS_PLAN, 0.95, f"document_type={document_type}")
        if document_type in _CONSULTANT_TYPES:
            return DomainResult(Domain.CONSULTANT_APPLICATION, 0.95, f"document_type={document_type}")

    bp_score = sum(1 for kw in _BP_KEYWORDS if kw.lower() in haystack)
    ca_score = sum(1 for kw in _CA_KEYWORDS if kw.lower() in haystack)

    if bp_score > ca_score and bp_score >= 2:
        conf = min(0.95, 0.5 + bp_score * 0.1)
        return DomainResult(Domain.BUSINESS_PLAN, conf, f"bp_keywords={bp_score}")
    if ca_score > bp_score and ca_score >= 2:
        conf = min(0.95, 0.5 + ca_score * 0.1)
        return DomainResult(Domain.CONSULTANT_APPLICATION, conf, f"ca_keywords={ca_score}")

    return DomainResult(Domain.OTHER, 0.3, "no_clear_domain_signal")
