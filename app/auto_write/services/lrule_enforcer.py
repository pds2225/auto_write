# lrule_enforcer.py — Full LRule enforcement engine
"""L규칙 전수 Enforcement 엔진.

모든 canonical L규칙을 runtime에서 판정하고 JSON report를 생성한다.
도메인/document_type 기반으로 applicable/non-applicable을 결정하며,
registry·guard·evidence가 불완전하면 fail-closed로 FINAL을 차단한다.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_write.domains.domain_classifier import Domain

__all__ = [
    "LRuleStatus",
    "LRuleEntry",
    "LRuleReport",
    "LRuleEnforcer",
    "enforce_lrules",
    "compute_sha256",
    "compute_registry_sha256",
]

# Allowed statuses
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NA = "N/A"
STATUS_REVIEW = "REVIEW_REQUIRED"
STATUS_UNVERIFIABLE = "UNVERIFIABLE"
STATUS_USER_OVERRIDE = "USER_OVERRIDE"

FINAL_BLOCKERS = {STATUS_FAIL, STATUS_REVIEW, STATUS_UNVERIFIABLE}
ALLOWED_STATUSES = {
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_NA,
    STATUS_REVIEW,
    STATUS_UNVERIFIABLE,
    STATUS_USER_OVERRIDE,
}
_LESSON_CATEGORIES = {"mechanized", "gap", "judgment"}
_LESSON_DOMAINS = {"all", *(domain.value for domain in Domain)}


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
    registry_issues: list[str] = field(default_factory=list)
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
            "registry_issues": self.registry_issues,
            "can_finalize": self.can_finalize,
            "finalization_blocked_reason": self.finalization_blocked_reason,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str | Path) -> Path:
        """현재 report를 JSON으로 저장한다.

        저장은 제출 판정의 일부이므로 호출자가 예외를 삼키면 안 된다.
        ``LRuleEnforcer``는 이 예외를 받아 report를 fail-closed로 바꾼다.
        """
        target = Path(path)
        if self.artifact_path and target.resolve() == Path(self.artifact_path).resolve():
            raise ValueError("lrule report가 artifact를 덮어쓸 수 없습니다")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.report_path = str(target)
        target.write_text(self.to_json() + "\n", encoding="utf-8")
        return target


def _compute_sha256(path: str | Path) -> str:
    """파일의 SHA256을 계산한다."""

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


compute_sha256 = _compute_sha256


def _compute_registry_sha256(lessons_path: str | Path) -> str:
    """lessons_coverage.json의 SHA256을 계산한다."""

    return _compute_sha256(lessons_path)


compute_registry_sha256 = _compute_registry_sha256


class LRuleEnforcer:
    """L규칙 전수 판정기."""

    def __init__(self, lessons_path: str | Path = None):
        if lessons_path is None:
            lessons_path = Path(__file__).parent.parent.parent / "tests" / "lessons_coverage.json"
        self.lessons_path = Path(lessons_path)
        self._lessons, self._registry_issues = self._load_lessons()

    def _load_lessons(self) -> tuple[list[dict], list[str]]:
        with open(self.lessons_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("LRule registry는 JSON object여야 합니다")

        raw_lessons = data.get("lessons", [])
        if not isinstance(raw_lessons, list):
            raise ValueError("LRule registry의 lessons는 list여야 합니다")

        lessons: list[dict] = []
        issues: list[str] = []
        ids: list[str] = []
        for index, raw_lesson in enumerate(raw_lessons):
            if not isinstance(raw_lesson, dict):
                issues.append(f"lesson[{index}] is not an object")
                lessons.append({"id": f"<invalid:{index}>"})
                continue

            lesson = dict(raw_lesson)
            lessons.append(lesson)
            rule_id = str(lesson.get("id", "")).strip()
            if rule_id:
                ids.append(rule_id)
            else:
                issues.append(f"lesson[{index}] missing id")
            for field_name in ("summary", "category", "domain"):
                if not str(lesson.get(field_name, "")).strip():
                    issues.append(f"{rule_id or f'lesson[{index}]'} missing {field_name}")

            category = str(lesson.get("category", "")).strip()
            if category and category not in _LESSON_CATEGORIES:
                issues.append(f"{rule_id or f'lesson[{index}]'} unknown category={category}")
            domain = str(lesson.get("domain", "")).strip()
            if domain and domain not in _LESSON_DOMAINS:
                issues.append(f"{rule_id or f'lesson[{index}]'} unknown domain={domain}")

        seen: set[str] = set()
        duplicate_ids: set[str] = set()
        for rule_id in ids:
            if rule_id in seen:
                duplicate_ids.add(rule_id)
            seen.add(rule_id)
        for rule_id in sorted(duplicate_ids):
            issues.append(f"duplicate rule id={rule_id}")

        declared_counts = data.get("counts")
        if isinstance(declared_counts, dict):
            declared_total = declared_counts.get("total")
            if isinstance(declared_total, int) and declared_total != len(lessons):
                direction = "missing" if declared_total > len(lessons) else "unexpected"
                issues.append(
                    f"registry counts.total={declared_total}, actual={len(lessons)} ({direction})"
                )
            for category in _LESSON_CATEGORIES:
                declared = declared_counts.get(category)
                actual = sum(1 for lesson in lessons if lesson.get("category") == category)
                if isinstance(declared, int) and declared != actual:
                    issues.append(f"registry counts.{category}={declared}, actual={actual}")
        return lessons, issues

    def enforce(
        self,
        domain: Domain,
        document_type: str = "",
        artifact_path: str | Path = "",
        guards: dict[str, Any] = None,
        report_path: str | Path = None,
        save_report: bool = True,
    ) -> LRuleReport:
        """모든 canonical L규칙을 판정하고 report를 생성한다.

        ``guards`` 값은 기존 호환성을 위해 결과 dict를 받으며, 실제 runtime
        배선을 위해 context keyword를 받는 callable도 허용한다. guard가 없거나
        malformed하면 PASS로 추정하지 않고 UNVERIFIABLE로 남긴다.
        """
        if guards is None:
            guards = {}
        if not isinstance(guards, dict):
            raise TypeError("guards는 rule id를 key로 하는 dict여야 합니다")

        if not isinstance(domain, Domain):
            try:
                domain = Domain(str(domain))
            except ValueError as exc:
                raise ValueError(f"알 수 없는 domain: {domain}") from exc

        artifact = Path(artifact_path) if artifact_path else None
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        artifact_hash = ""
        if artifact is not None and artifact.exists():
            artifact_hash = _compute_sha256(artifact)
        registry_hash = _compute_registry_sha256(self.lessons_path)

        entries: list[LRuleEntry] = []
        summary = {
            "total": 0,
            "pass": 0,
            "na": 0,
            "fail": 0,
            "review_required": 0,
            "unverifiable": 0,
            "user_override": 0,
            "missing": sum(1 for issue in self._registry_issues if "missing" in issue),
            "duplicate": sum(1 for issue in self._registry_issues if "duplicate" in issue),
            "invalid": 0,
        }
        summary["invalid"] = len(self._registry_issues) - summary["missing"] - summary["duplicate"]

        known_ids = {
            str(lesson.get("id", "")).strip()
            for lesson in self._lessons
            if str(lesson.get("id", "")).strip()
        }
        unknown_guard_ids = sorted(set(guards) - known_ids)
        if unknown_guard_ids:
            summary["invalid"] += len(unknown_guard_ids)

        for lesson in self._lessons:
            rule_id = str(lesson.get("id", "?")).strip() or "?"
            rule_title = str(lesson.get("summary", ""))
            rule_domain = str(lesson.get("domain", "all"))
            category = str(lesson.get("category", "judgment"))
            guard_ref = str(lesson.get("guard_ref", ""))
            applicable = self._is_applicable(rule_domain, domain)

            if not applicable:
                status = STATUS_NA
                reason = f"rule belongs to {rule_domain}, not {domain.value}"
                evidence = ""
                reviewer = "n/a"
            elif rule_id in guards:
                status, evidence, reason = self._evaluate_guard(
                    guards[rule_id], domain=domain, document_type=document_type,
                    artifact_path=artifact_path, lesson=lesson,
                )
                reviewer = "user" if status == STATUS_USER_OVERRIDE else "auto"
            elif category == "mechanized":
                status = STATUS_UNVERIFIABLE
                evidence = ""
                reason = f"mechanized guard_ref={guard_ref} but no callable provided"
                reviewer = "auto"
            elif category == "gap":
                status = STATUS_REVIEW
                evidence = ""
                reason = "no automated guard available"
                reviewer = "auto"
            else:
                status = STATUS_REVIEW
                evidence = ""
                reason = "judgment rule requires human evidence"
                reviewer = "auto"

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
                reviewer=reviewer,
            )
            entries.append(entry)
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

        can_finalize = True
        block_reasons: list[str] = []
        if summary["fail"] > 0:
            can_finalize = False
            block_reasons.append(f"{summary['fail']} FAIL rules")
        if summary["review_required"] > 0:
            can_finalize = False
            block_reasons.append(f"{summary['review_required']} REVIEW_REQUIRED rules")
        if summary["unverifiable"] > 0:
            can_finalize = False
            block_reasons.append(f"{summary['unverifiable']} UNVERIFIABLE rules")
        if summary["missing"] > 0 or summary["duplicate"] > 0 or summary["invalid"] > 0:
            can_finalize = False
            block_reasons.append(
                f"invalid registry: missing={summary['missing']} "
                f"duplicate={summary['duplicate']} invalid={summary['invalid']}"
            )
        if unknown_guard_ids:
            can_finalize = False
            block_reasons.append(f"unknown guard ids: {', '.join(unknown_guard_ids)}")
        if not artifact_hash:
            can_finalize = False
            block_reasons.append("artifact hash unavailable")

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
            rules=[entry.as_dict() for entry in entries],
            registry_issues=list(self._registry_issues),
            can_finalize=can_finalize,
            finalization_blocked_reason="; ".join(block_reasons),
        )

        if save_report:
            target = Path(report_path) if report_path else (
                artifact.with_name("lrule_report.json") if artifact is not None else None
            )
            if target is not None:
                try:
                    report.save(target)
                except Exception as exc:
                    report.can_finalize = False
                    report.finalization_blocked_reason = (
                        f"{report.finalization_blocked_reason}; " if report.finalization_blocked_reason else ""
                    ) + f"lrule report save failed: {type(exc).__name__}: {exc}"

        return report

    @classmethod
    def _evaluate_guard(
        cls,
        guard: Any,
        *,
        domain: Domain,
        document_type: str,
        artifact_path: str | Path,
        lesson: dict[str, Any],
    ) -> tuple[str, str, str]:
        if callable(guard):
            try:
                guard = guard(
                    domain=domain,
                    document_type=document_type,
                    artifact_path=artifact_path,
                    lesson=lesson,
                )
            except Exception as exc:
                return STATUS_UNVERIFIABLE, "", f"guard raised {type(exc).__name__}: {exc}"
        if not isinstance(guard, dict):
            return STATUS_UNVERIFIABLE, "", "guard result must be a dict or callable returning a dict"
        return cls._status_from_guard(guard)

    @staticmethod
    def _status_from_guard(guard_result: dict[str, Any]) -> tuple[str, str, str]:
        """Guard 결과를 허용된 상태로 정규화하고 상태 불변조건을 적용한다."""
        explicit_status = str(guard_result.get("status", "")).strip().upper()
        evidence = str(guard_result.get("evidence", "") or "").strip()
        reason = str(guard_result.get("reason", "") or "").strip()

        if explicit_status:
            if explicit_status not in ALLOWED_STATUSES:
                return STATUS_UNVERIFIABLE, evidence, f"unknown guard status={explicit_status}"
            if explicit_status == STATUS_PASS and not evidence:
                return STATUS_REVIEW, "", "PASS requires evidence"
            if explicit_status == STATUS_NA and not reason:
                return STATUS_REVIEW, evidence, "N/A requires reason"
            if explicit_status == STATUS_USER_OVERRIDE:
                if not guard_result.get("user_approved") or not evidence:
                    return STATUS_REVIEW, evidence, "USER_OVERRIDE requires user_approved and evidence"
            return explicit_status, evidence, reason

        passed = guard_result.get("passed")
        if passed is True:
            if not evidence:
                return STATUS_REVIEW, "", "PASS requires evidence"
            return STATUS_PASS, evidence, reason
        if passed is False:
            return STATUS_FAIL, evidence or "guard failed", reason
        return STATUS_UNVERIFIABLE, evidence, reason or "guard result missing passed/status"

    @staticmethod
    def _is_applicable(rule_domain: str, target_domain: Domain) -> bool:
        """규칙이 대상 도메인에 적용 가능한지 판정한다."""
        return rule_domain == "all" or rule_domain == target_domain.value


def enforce_lrules(
    domain: Domain,
    document_type: str = "",
    artifact_path: str | Path = "",
    guards: dict[str, Any] = None,
    lessons_path: str | Path = None,
    report_path: str | Path = None,
    save_report: bool = True,
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
