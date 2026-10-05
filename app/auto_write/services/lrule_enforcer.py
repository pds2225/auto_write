# lrule_enforcer.py — Full LRule enforcement engine
"""L규칙 전수 Enforcement 엔진.

모든 canonical L규칙을 runtime에서 판정하고 JSON report를 생성한다.
domain/document_type 기반으로 applicable/non-applicable을 결정하고,
fail-closed 원칙에 따라 FINAL을 차단한다.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from auto_write.domains.domain_classifier import Domain

_RULE_CODE_RE = re.compile(r"\bL\d{3}\b", re.IGNORECASE)


def rule_code(rule_id: str) -> str:
    """'L009 | …' 또는 'L009' 에서 규칙 코드를 뽑는다."""
    match = _RULE_CODE_RE.search(str(rule_id or ""))
    return match.group(0).upper() if match else str(rule_id or "").strip()


def lookup_guard(rule_id: str, guards: dict[str, Any] | None) -> dict[str, Any] | None:
    """전체 id 또는 Lxxx 코드로 가드 결과를 찾는다."""
    if not guards:
        return None
    if rule_id in guards:
        return guards[rule_id]
    code = rule_code(rule_id)
    if code and code in guards:
        return guards[code]
    return None

__all__ = [
    "LRuleStatus",
    "LRuleEntry",
    "LRuleReport",
    "LRuleEnforcer",
    "enforce_lrules",
    "rule_code",
    "lookup_guard",
]

# Allowed statuses
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NA = "N/A"
STATUS_REVIEW = "REVIEW_REQUIRED"
STATUS_UNVERIFIABLE = "UNVERIFIABLE"
STATUS_USER_OVERRIDE = "USER_OVERRIDE"

FINAL_BLOCKERS = {STATUS_FAIL, STATUS_REVIEW, STATUS_UNVERIFIABLE}
ALLOWED_STATUSES = {STATUS_PASS, STATUS_FAIL, STATUS_NA, STATUS_REVIEW,
                    STATUS_UNVERIFIABLE, STATUS_USER_OVERRIDE}


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
    registry_path: str = ""
    report_path: str = ""
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
            "registry_path": self.registry_path,
            "report_path": self.report_path,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "rules": self.rules,
            "can_finalize": self.can_finalize,
            "finalization_blocked_reason": self.finalization_blocked_reason,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str | Path) -> Path:
        """검사 증거를 저장하며 원본 산출물·규칙 원장은 보호한다."""
        target = Path(path)
        for original in (self.artifact_path, self.registry_path):
            if original and target.resolve() == Path(original).resolve():
                raise ValueError("LRule report가 원본 파일을 덮어쓸 수 없습니다")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.report_path = str(target)
        target.write_text(self.to_json() + "\n", encoding="utf-8")
        return target


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
        if not isinstance(data, dict) or not isinstance(data.get("lessons", []), list):
            raise ValueError("LRule registry는 lessons 배열을 포함한 JSON object여야 합니다")
        lessons = data.get("lessons", [])
        self._registry_issues = []
        for index, lesson in enumerate(lessons):
            if not isinstance(lesson, dict):
                raise ValueError(f"lesson[{index}] is not an object")
            for key in ("id", "summary", "category", "domain"):
                if not str(lesson.get(key, "")).strip():
                    self._registry_issues.append(f"lesson[{index}] missing {key}")
            if lesson.get("category") not in {"mechanized", "gap", "judgment"}:
                self._registry_issues.append(f"lesson[{index}] unknown category")
            if lesson.get("domain") not in {"all", *(domain.value for domain in Domain)}:
                self._registry_issues.append(f"lesson[{index}] unknown domain")
        counts = data.get("counts", {})
        if isinstance(counts, dict):
            total = counts.get("total")
            if isinstance(total, int) and total != len(lessons):
                direction = "missing" if total > len(lessons) else "unexpected"
                self._registry_issues.append(f"counts.total={total}, actual={len(lessons)} ({direction})")
            for category in ("mechanized", "gap", "judgment"):
                declared = counts.get(category)
                actual = sum(lesson.get("category") == category for lesson in lessons)
                if isinstance(declared, int) and declared != actual:
                    self._registry_issues.append(f"counts.{category}={declared}, actual={actual}")
        return lessons

    def enforce(
        self,
        domain: Domain,
        document_type: str = "",
        artifact_path: str | Path = "",
        guards: dict[str, Any] = None,
        report_path: str | Path = None,
        save_report: bool = False,
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
        if not isinstance(guards, dict):
            raise TypeError("guards는 rule id를 key로 하는 dict여야 합니다")

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
        seen_ids: set[str] = set()
        duplicate_ids: list[str] = []
        summary = {
            "total": 0,
            "pass": 0,
            "na": 0,
            "fail": 0,
            "review_required": 0,
            "unverifiable": 0,
            "user_override": 0,
            "missing": sum("missing" in issue for issue in self._registry_issues),
            "duplicate": 0,
            "invalid": sum("missing" not in issue for issue in self._registry_issues),
        }
        known_ids = {str(lesson.get("id", "")) for lesson in self._lessons}
        known_ids.update(rule_code(rule_id) for rule_id in tuple(known_ids))
        unknown_guard_ids = sorted(str(key) for key in guards if key not in known_ids)
        summary["invalid"] += len(unknown_guard_ids)

        for lesson in self._lessons:
            rule_id = lesson.get("id", "?")
            if rule_id in seen_ids:
                duplicate_ids.append(rule_id)
            seen_ids.add(rule_id)
            rule_title = lesson.get("summary", "")
            rule_domain = lesson.get("domain", "all")
            category = lesson.get("category", "judgment")
            guard_ref = lesson.get("guard_ref", "")

            # Determine applicability
            applicable = self._is_applicable(rule_domain, domain)
            guard_result = lookup_guard(rule_id, guards)

            # Determine status
            if not applicable:
                status = STATUS_NA
                reason = f"rule belongs to {rule_domain}, not {domain.value}"
                evidence = ""
            elif guard_result is not None:
                status, evidence, reason = self._evaluate_guard(
                    guard_result, domain=domain, document_type=document_type,
                    artifact_path=artifact_path, lesson=lesson,
                )
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
                reviewer=("user" if status == STATUS_USER_OVERRIDE else "auto") if applicable else "n/a",
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
        summary["duplicate"] = len(set(duplicate_ids))
        can_finalize = True
        block_reason = ""

        if not self._lessons or summary["total"] == 0:
            can_finalize = False
            block_reason = "LRule report missing or empty"
        elif duplicate_ids:
            can_finalize = False
            uniq = ",".join(sorted(set(duplicate_ids)))
            block_reason = f"duplicate LRule ids: {uniq}"
        elif summary["fail"] > 0:
            can_finalize = False
            block_reason = f"{summary['fail']} FAIL rules"
        elif summary["review_required"] > 0:
            can_finalize = False
            block_reason = f"{summary['review_required']} REVIEW_REQUIRED rules"
        elif summary["unverifiable"] > 0:
            can_finalize = False
            block_reason = f"{summary['unverifiable']} UNVERIFIABLE rules"

        if self._registry_issues or unknown_guard_ids:
            can_finalize = False
            detail = (f"invalid registry: missing={summary['missing']} "
                      f"duplicate={summary['duplicate']} invalid={summary['invalid']}")
            block_reason = f"{block_reason}; {detail}".strip("; ")
            if unknown_guard_ids:
                block_reason += f"; unknown guard ids: {', '.join(unknown_guard_ids)}"
        elif duplicate_ids:
            block_reason += f"; duplicate={summary['duplicate']}"

        if artifact_path and Path(artifact_path).exists():
            end_hash = _compute_sha256(artifact_path)
            if artifact_hash and end_hash != artifact_hash:
                can_finalize = False
                block_reason = "artifact SHA256 changed during enforcement"
                artifact_hash = end_hash

        report = LRuleReport(
            run_id=run_id,
            domain=domain.value,
            document_type=document_type,
            artifact_path=str(artifact_path),
            artifact_sha256=artifact_hash,
            registry_sha256=registry_hash,
            registry_path=str(self.lessons_path),
            timestamp=now,
            summary=summary,
            rules=[e.as_dict() for e in entries],
            can_finalize=can_finalize,
            finalization_blocked_reason=block_reason,
        )

        if save_report or report_path is not None:
            target = Path(report_path) if report_path else (
                Path(artifact_path).with_name("lrule_report.json") if artifact_path else None
            )
            try:
                if target is None:
                    raise ValueError("LRule report 저장 경로가 없습니다")
                report.save(target)
            except Exception as exc:
                report.can_finalize = False
                detail = f"lrule report save failed: {type(exc).__name__}: {exc}"
                report.finalization_blocked_reason = f"{report.finalization_blocked_reason}; {detail}".strip("; ")
        return report

    @classmethod
    def _evaluate_guard(cls, guard: Any, **context: Any) -> tuple[str, str, str]:
        if callable(guard):
            try:
                guard = guard(**context)
            except Exception as exc:
                return STATUS_UNVERIFIABLE, "", f"guard raised {type(exc).__name__}: {exc}"
        if not isinstance(guard, dict):
            return STATUS_UNVERIFIABLE, "", "guard result must be a dict or callable returning a dict"
        status = str(guard.get("status", "")).strip().upper()
        evidence = str(guard.get("evidence", "") or "").strip()
        reason = str(guard.get("reason", "") or "").strip()
        if status:
            if status not in ALLOWED_STATUSES:
                return STATUS_UNVERIFIABLE, evidence, f"unknown guard status={status}"
            if status == STATUS_PASS and "passed" in guard and guard["passed"] is not True:
                return STATUS_UNVERIFIABLE, evidence, "PASS contradicts passed result"
            if status == STATUS_PASS and not evidence:
                return STATUS_REVIEW, "", "PASS requires evidence"
            if status == STATUS_NA and not reason:
                return STATUS_REVIEW, evidence, "N/A requires reason"
            if status == STATUS_USER_OVERRIDE and (guard.get("user_approved") is not True or not evidence):
                return STATUS_REVIEW, evidence, "USER_OVERRIDE requires user_approved and evidence"
            return status, evidence, reason
        if guard.get("passed") is True:
            return (STATUS_PASS, evidence, reason) if evidence else (STATUS_REVIEW, "", "PASS requires evidence")
        if guard.get("passed") is False:
            return STATUS_FAIL, evidence or "guard failed", reason
        return STATUS_UNVERIFIABLE, evidence, reason or "guard result missing passed/status"

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
    report_path: str | Path = None,
    save_report: bool = False,
) -> LRuleReport:
    """편의 함수 — L규칙을 전수 판정한다."""
    enforcer = LRuleEnforcer(lessons_path)
    return enforcer.enforce(
        domain=domain,
        document_type=document_type,
        artifact_path=artifact_path,
        guards=guards,
        report_path=report_path,
        save_report=save_report,
    )
