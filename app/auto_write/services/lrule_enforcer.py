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
from auto_write.services.lrule_fill_check import (
    FillReport, format_locations, inspect_fill, is_fill_rule,
)

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
    "three_stage_text",
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
    # 3단계 판정(해당 → 채움 → 통과). 기존 필드는 그대로 두고 아래만 추가했다.
    filled: Optional[bool] = None   # None = 채움 판정 대상 아님/미검사
    passed: Optional[bool] = None   # True=PASS, False=FAIL, None=미판정(REVIEW 등)
    na_reason: str = ""
    na_evidenced: Optional[bool] = None  # N/A 일 때만 True(근거 있음). 근거 없는 N/A 는 FAIL 로 바뀐다.
    location: str = ""              # 위치·셀 정보
    basis: str = ""                 # "process"=산출물 검증 없는 프로세스 불변식 통과

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
            "filled": self.filled,
            "passed": self.passed,
            "na_reason": self.na_reason,
            "na_evidenced": self.na_evidenced,
            "location": self.location,
            "basis": self.basis,
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
            "summary_text": self.summary_text(),
            "rules": self.rules,
            "can_finalize": self.can_finalize,
            "finalization_blocked_reason": self.finalization_blocked_reason,
        }

    def summary_text(self) -> str:
        """사람이 읽는 3단계 집계 한 줄(해당·채움·통과·N/A 근거 유무)."""
        return three_stage_text(self.summary)

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


def three_stage_text(summary: dict) -> str:
    """summary 의 3단계 집계를 한국어 한 줄로 만든다."""
    g = summary.get
    return (
        f"해당 {g('applicable', 0)} · 채움 {g('filled', 0)}/{g('fill_required', 0)} "
        f"· 통과 {g('passed_verified', 0) + g('passed_process', 0)}"
        f"(산출물 검증 {g('passed_verified', 0)}·프로세스 {g('passed_process', 0)}) "
        f"· 실패 {g('fail', 0)} · N/A 근거있음 {g('na_evidenced', 0)}/근거없음 {g('na_unevidenced', 0)}"
    )


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
            # 3단계 집계: 해당 → 채움 → 통과, 그리고 N/A 근거 유무
            "applicable": 0,
            "fill_required": 0,
            "filled": 0,
            "passed_verified": 0,
            "passed_process": 0,
            "na_evidenced": 0,
            "na_unevidenced": 0,
        }
        fill_cache: dict[str, Optional[FillReport]] = {}
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

            code = rule_code(rule_id)
            domain_applicable = self._is_applicable(rule_domain, domain)
            guard_result = lookup_guard(rule_id, guards)
            filled: Optional[bool] = None
            na_reason = location = basis = ""
            na_evidenced: Optional[bool] = None

            # 1단계 — 해당 여부. N/A 는 근거(위치·출처)가 있어야 하고, 없으면 FAIL.
            if not domain_applicable:
                status = STATUS_NA
                reason = f"rule belongs to {rule_domain}, not {domain.value}"
                evidence = f"registry {code}: domain={rule_domain} != target domain={domain.value}"
                location = f"registry:{code}"
                na_reason, na_evidenced = reason, True
            elif guard_result is not None:
                verdict = self._evaluate_guard_full(
                    guard_result, domain=domain, document_type=document_type,
                    artifact_path=artifact_path, lesson=lesson,
                )
                status, evidence, reason = verdict["status"], verdict["evidence"], verdict["reason"]
                location, basis = verdict["location"], verdict["basis"]
                if status == STATUS_NA or basis == "skipped_format":
                    na_reason, na_evidenced = reason, True
                if verdict["na_unevidenced"]:
                    summary["na_unevidenced"] += 1
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

            # 2단계 — 채움 여부. 해당이고 채움 대상 규칙이면 빈칸·안내문 잔존을 즉시 FAIL 로 본다.
            if domain_applicable and status != STATUS_NA and is_fill_rule(code):
                fill = fill_cache.get("report")
                if fill is None:
                    fill = fill_cache["report"] = self._inspect_fill(artifact_path)
                if fill is not None and fill.supported and fill.error:
                    status, evidence = STATUS_UNVERIFIABLE, ""
                    reason = f"fill inspection failed: {fill.error}"
                elif fill is not None and fill.supported:
                    found = fill.for_rule(code)
                    filled = not found
                    if found:
                        status = STATUS_FAIL
                        location = format_locations(found)
                        evidence = location
                        reason = f"미채움 {len(found)}건 — 빈칸·안내문·반복칸·미선택 중 하나 이상 남음"
                    else:
                        location = location or f"표 {fill.tables}개·칸 {fill.cells}개 검사"

            # 3단계 — 통과 여부(앞 단계가 막히면 PASS 불가).
            applicable = domain_applicable  # 기존 소비자 호환: 도메인 기준 해당 여부
            counts_as_na = status == STATUS_NA or basis == "skipped_format"
            passed_flag = (
                None if counts_as_na else True if status == STATUS_PASS else False if status == STATUS_FAIL else None
            )

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
                filled=filled,
                passed=passed_flag,
                na_reason=na_reason,
                na_evidenced=na_evidenced,
                location=location,
                basis=basis,
            )
            entries.append(entry)

            # Update summary
            summary["total"] += 1
            if applicable and not counts_as_na:
                summary["applicable"] += 1  # 실제 판정 대상(근거 있는 N/A 제외)
            if counts_as_na:
                summary["na_evidenced"] += 1
            if filled is not None:
                summary["fill_required"] += 1
                if filled:
                    summary["filled"] += 1
            if status == STATUS_PASS:
                summary["pass"] += 1
                if basis == "process":
                    summary["passed_process"] += 1
                elif basis != "skipped_format":
                    summary["passed_verified"] += 1
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

    @staticmethod
    def _inspect_fill(artifact_path: str | Path) -> Optional[FillReport]:
        """채움 검사. 산출물이 없으면 검사하지 않는다(None → 채움 판정 보류)."""
        if not artifact_path or not Path(artifact_path).is_file():
            return None
        return inspect_fill(artifact_path)

    @classmethod
    def _evaluate_guard(cls, guard: Any, **context: Any) -> tuple[str, str, str]:
        """호환용: (status, evidence, reason) 만 돌려준다."""
        verdict = cls._evaluate_guard_full(guard, **context)
        return verdict["status"], verdict["evidence"], verdict["reason"]

    @classmethod
    def _evaluate_guard_full(cls, guard: Any, **context: Any) -> dict[str, Any]:
        """가드 결과를 status·evidence·reason·location·basis 로 정규화한다.

        N/A 는 reason 과 근거(evidence 또는 location) 가 모두 있어야 인정한다.
        하나라도 없으면 근거 없는 N/A 로 보고 FAIL 로 바꾼다.
        """
        def out(status: str, evidence: str = "", reason: str = "", *, location: str = "",
                basis: str = "", na_unevidenced: bool = False) -> dict[str, Any]:
            return {"status": status, "evidence": evidence, "reason": reason,
                    "location": location, "basis": basis, "na_unevidenced": na_unevidenced}

        if callable(guard):
            try:
                guard = guard(**context)
            except Exception as exc:
                return out(STATUS_UNVERIFIABLE, "", f"guard raised {type(exc).__name__}: {exc}")
        if not isinstance(guard, dict):
            return out(STATUS_UNVERIFIABLE, "", "guard result must be a dict or callable returning a dict")
        status = str(guard.get("status", "")).strip().upper()
        evidence = str(guard.get("evidence", "") or "").strip()
        reason = str(guard.get("reason", "") or "").strip()
        location = str(guard.get("location", "") or "").strip()
        basis = str(guard.get("basis", "") or "").strip()
        if status:
            if status not in ALLOWED_STATUSES:
                return out(STATUS_UNVERIFIABLE, evidence, f"unknown guard status={status}")
            if status == STATUS_PASS and "passed" in guard and guard["passed"] is not True:
                return out(STATUS_UNVERIFIABLE, evidence, "PASS contradicts passed result")
            if status == STATUS_PASS and not evidence:
                return out(STATUS_REVIEW, "", "PASS requires evidence")
            if status == STATUS_NA:
                if not reason or not (evidence or location):
                    missing = "reason" if not reason else "evidence/location"
                    return out(STATUS_FAIL, evidence or location, f"근거 없는 N/A: {missing} 없음",
                               location=location, na_unevidenced=True)
                return out(STATUS_NA, evidence or location, reason, location=location)
            if status == STATUS_USER_OVERRIDE and (guard.get("user_approved") is not True or not evidence):
                return out(STATUS_REVIEW, evidence, "USER_OVERRIDE requires user_approved and evidence")
            return out(status, evidence, reason, location=location, basis=basis)
        if guard.get("passed") is True:
            if evidence:
                return out(STATUS_PASS, evidence, reason, location=location, basis=basis)
            return out(STATUS_REVIEW, "", "PASS requires evidence")
        if guard.get("passed") is False:
            return out(STATUS_FAIL, evidence or "guard failed", reason, location=location)
        return out(STATUS_UNVERIFIABLE, evidence, reason or "guard result missing passed/status")

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
