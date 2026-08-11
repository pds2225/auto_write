# lrule_enforcer.py — Full LRule enforcement engine
"""L규칙 전수 Enforcement 엔진.

모든 canonical L규칙을 runtime에서 판정하고 JSON report를 생성한다.
domain/document_type 기반으로 applicable/non-applicable을 결정하고,
fail-closed 원칙에 따라 FINAL을 차단한다.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from auto_write.domains.domain_classifier import Domain

__all__ = [
    "LRuleStatus",
    "LRuleEntry",
    "LRuleReport",
    "LRuleEnforcer",
    "enforce_lrules",
]

# Allowed statuses
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NA = "N/A"
STATUS_REVIEW = "REVIEW_REQUIRED"
STATUS_UNVERIFIABLE = "UNVERIFIABLE"
STATUS_USER_OVERRIDE = "USER_OVERRIDE"

FINAL_BLOCKERS = {STATUS_FAIL, STATUS_REVIEW, STATUS_UNVERIFIABLE}


@dataclass
class LRuleStatus:
    """규칙 상태를 나타내는 값 객체."""
    status: str
    evidence: str = ""
    reason: str = ""

    def is_final_blocker(self) -> bool:
        return self.status in FINAL_BLOCKERS


@dataclass
class LRuleEntry:
    """단일 L규칙 판정 결과."""
    id: str
    title: str
    domain: str
    applicable: bool
    status: str
    phase: str
    guard: str
    evidence: str
    reason: str
    reviewer: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "applicable": self.applicable,
            "status": self.status,
            "phase": self.phase,
            "guard": self.guard,
            "evidence": self.evidence,
            "reason": self.reason,
            "reviewer": self.reviewer,
        }


@dataclass
class LRuleReport:
    """L규칙 전수 판정 report."""
    run_id: str = ""
    domain: str = ""
    document_type: str = ""
    artifact_path: str = ""
    artifact_sha256: str = ""
    registry_sha256: str = ""
    timestamp: str = ""
    summary: dict = field(default_factory=dict)
    rules: list[dict] = field(default_factory=list)
    can_finalize: bool = False
    finalization_blocked_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "domain": self.domain,
            "document_type": self.document_type,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "registry_sha256": self.registry_sha256,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "rules": self.rules,
            "can_finalize": self.can_finalize,
            "finalization_blocked_reason": self.finalization_blocked_reason,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=indent)


def _compute_sha256(path: str | Path) -> str:
    """파일의 SHA256 해시를 계산한다."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_registry_sha256(lessons_path: str | Path) -> str:
    """lessons_coverage.json의 SHA256을 계산한다."""
    return _compute_sha256(lessons_path)


class LRuleEnforcer:
    """L규칙 전수 Enforcement 엔진."""

    def __init__(self, lessons_path: str | Path = None):
        if lessons_path is None:
            lessons_path = Path(__file__).parent.parent.parent / "tests" / "lessons_coverage.json"
        self.lessons_path = Path(lessons_path)
        self._lessons = self._load_lessons()

    def _load_lessons(self) -> list[dict]:
        with open(self.lessons_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("lessons", [])

    def enforce(
        self,
        domain: Domain,
        document_type: str = "",
        artifact_path: str | Path = "",
        guards: dict[str, Any] = None,
    ) -> LRuleReport:
        """모든 canonical L규칙을 판정하고 report를 생성한다.

        Args:
            domain: 판정 대상 도메인
            document_type: 문서 유형
            artifact_path: 검사 대상 artifact 경로
            guards: 규칙 ID → guard 실행 결과 매핑
        """
        if guards is None:
            guards = {}

        run_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        # Artifact SHA256
        artifact_hash = ""
        if artifact_path and Path(artifact_path).exists():
            artifact_hash = _compute_sha256(artifact_path)

        # Registry SHA256
        registry_hash = _compute_registry_sha256(self.lessons_path)

        # Evaluate each rule
        entries: list[LRuleEntry] = []
        summary = {
            "total": 0,
            "pass": 0,
            "na": 0,
            "fail": 0,
            "review_required": 0,
            "unverifiable": 0,
            "user_override": 0,
        }

        for lesson in self._lessons:
            rule_id = lesson.get("id", "?")
            rule_title = lesson.get("summary", "")
            rule_domain = lesson.get("domain", "all")
            category = lesson.get("category", "judgment")
            guard_ref = lesson.get("guard_ref", "")

            # Determine applicability
            applicable = self._is_applicable(rule_domain, domain)

            # Determine status
            if not applicable:
                status = STATUS_NA
                reason = f"rule belongs to {rule_domain}, not {domain.value}"
                evidence = ""
            elif rule_id in guards:
                guard_result = guards[rule_id]
                if guard_result.get("passed", False):
                    status = STATUS_PASS
                    evidence = guard_result.get("evidence", "guard passed")
                    reason = ""
                else:
                    status = STATUS_FAIL
                    evidence = guard_result.get("evidence", "guard failed")
                    reason = guard_result.get("reason", "")
            elif category == "mechanized":
                # Mechanized but no guard callable → UNVERIFIABLE
                status = STATUS_UNVERIFIABLE
                evidence = ""
                reason = f"mechanized guard_ref={guard_ref} but no callable provided"
            elif category == "gap":
                # Gap without guard → REVIEW_REQUIRED
                status = STATUS_REVIEW
                evidence = ""
                reason = "no automated guard available"
            else:
                # Judgment without evidence → REVIEW_REQUIRED
                status = STATUS_REVIEW
                evidence = ""
                reason = "judgment rule requires human evidence"

            entry = LRuleEntry(
                id=rule_id,
                title=rule_title,
                domain=rule_domain,
                applicable=applicable,
                status=status,
                phase=category,
                guard=guard_ref,
                evidence=evidence,
                reason=reason,
                reviewer="auto" if applicable else "n/a",
            )
            entries.append(entry)

            # Update summary
            summary["total"] += 1
            if status == STATUS_PASS:
                summary["pass"] += 1
            elif status == STATUS_NA:
                summary["na"] += 1
            elif status == STATUS_FAIL:
                summary["fail"] += 1
            elif status == STATUS_REVIEW:
                summary["review_required"] += 1
            elif status == STATUS_UNVERIFIABLE:
                summary["unverifiable"] += 1
            elif status == STATUS_USER_OVERRIDE:
                summary["user_override"] += 1

        # Finalization check
        can_finalize = True
        block_reason = ""

        if summary["fail"] > 0:
            can_finalize = False
            block_reason = f"{summary['fail']} FAIL rules"
        elif summary["review_required"] > 0:
            can_finalize = False
            block_reason = f"{summary['review_required']} REVIEW_REQUIRED rules"
        elif summary["unverifiable"] > 0:
            can_finalize = False
            block_reason = f"{summary['unverifiable']} UNVERIFIABLE rules"

        if artifact_path and artifact_hash:
            # Hash mismatch check would go here
            pass

        report = LRuleReport(
            run_id=run_id,
            domain=domain.value,
            document_type=document_type,
            artifact_path=str(artifact_path),
            artifact_sha256=artifact_hash,
            registry_sha256=registry_hash,
            timestamp=now,
            summary=summary,
            rules=[e.as_dict() for e in entries],
            can_finalize=can_finalize,
            finalization_blocked_reason=block_reason,
        )

        return report

    def _is_applicable(self, rule_domain: str, target_domain: Domain) -> bool:
        """규칙이 대상 도메인에 적용 가능한지 판별한다."""
        if rule_domain == "all":
            return True
        if rule_domain == target_domain.value:
            return True
        return False


def enforce_lrules(
    domain: Domain,
    document_type: str = "",
    artifact_path: str | Path = "",
    guards: dict[str, Any] = None,
    lessons_path: str | Path = None,
) -> LRuleReport:
    """편의 함수 — L규칙을 전수 판정한다."""
    enforcer = LRuleEnforcer(lessons_path)
    return enforcer.enforce(
        domain=domain,
        document_type=document_type,
        artifact_path=artifact_path,
        guards=guards,
    )
