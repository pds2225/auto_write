"""STEP 2 → STEP 3A 만남점: Fact / NarrativeEvidence / Conflict 출력 계약.

이 모듈은 HWP를 읽거나 추출기를 구현하지 않는다.
다른 세션의 STEP 2가 최종적으로 돌려줘야 하는 JSON:

{
  "facts": [{
    "fact_id": "...",                  # 필수. 없으면 만들지 않는다.
    "category": "PROBLEM|REVENUE|...",
    "canonical_field" | "label": "...",
    "value": ...,
    "semantic_state": "ACTUAL|PLAN|ESTIMATE|HYPOTHESIS|UNKNOWN|NOT_APPLICABLE|CONFLICT",
    "verification_state": "CONFIRMED|INFERRED|UNKNOWN|CONFLICT|NOT_APPLICABLE|REVIEW_REQUIRED|STALE|UNVERIFIABLE|INTERNAL_CONFLICT",
    "sources": [{"source_file": "...", "source_location": "..."}]
  }],
  "narrative_evidence": [{
    "evidence_id": "...",              # 필수
    "category": "...",
    "text": "...",
    "verification_state": "...",
    "source_file": "...",
    "source_location": "..."           # 또는 locator / sources[]
  }],
  "conflicts": [{
    "conflict_id": "...",
    "candidate_fact_ids": ["..."],     # 존재하는 fact_id만
    "reason": "..."
  }]
}

없는 semantic/verification 상태는 UNKNOWN으로 정규화한다. matcher는 UNKNOWN/CONFLICT를
자동 선택하지 않는다. ACTUAL과 PLAN을 한 값에 섞지 않는다. winner를 고르지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


SEMANTIC_STATES = frozenset({
    "ACTUAL",
    "PLAN",
    "ESTIMATE",
    "HYPOTHESIS",
    "UNKNOWN",
    "NOT_APPLICABLE",
    "CONFLICT",
})

VERIFICATION_STATES = frozenset({
    "CONFIRMED",
    "INFERRED",
    "UNKNOWN",
    "CONFLICT",
    "NOT_APPLICABLE",
    "REVIEW_REQUIRED",
    "STALE",
    "UNVERIFIABLE",
    "INTERNAL_CONFLICT",
})


class Step2ContractError(ValueError):
    """STEP 2 출력이 matcher 계약을 깨면 발생한다."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper().replace("-", "_").replace(" ", "_")


def _first(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


@dataclass(frozen=True)
class SourceRef:
    source_file: str
    source_location: str = ""
    locator: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source_file": self.source_file,
            "source_location": self.source_location,
        }
        if self.locator:
            out["locator"] = dict(self.locator)
        return out

    def has_location(self) -> bool:
        if self.source_location:
            return True
        return bool(self.locator)


def _parse_sources(item: dict[str, Any], *, label: str) -> list[SourceRef]:
    raw = item.get("sources")
    sources: list[SourceRef] = []
    if isinstance(raw, list):
        for index, row in enumerate(raw):
            if not isinstance(row, dict):
                raise Step2ContractError(f"{label}.sources[{index}]는 object여야 합니다.")
            source_file = _text(row.get("source_file"))
            location = _text(_first(row, ("source_location", "location")))
            locator = row.get("locator") if isinstance(row.get("locator"), dict) else None
            if locator == {}:
                locator = None
            if not source_file and not location and not locator:
                continue
            sources.append(SourceRef(source_file=source_file, source_location=location, locator=locator))
    file_fallback = _text(item.get("source_file"))
    location_fallback = _text(_first(item, ("source_location", "location")))
    locator_fallback = item.get("locator") if isinstance(item.get("locator"), dict) else None
    if locator_fallback == {}:
        locator_fallback = None
    if file_fallback or location_fallback or locator_fallback:
        fallback = SourceRef(
            source_file=file_fallback,
            source_location=location_fallback,
            locator=locator_fallback,
        )
        if fallback not in sources:
            sources.append(fallback)
    return sources


def _require_state(value: Any, allowed: frozenset[str], *, label: str, optional: bool = False) -> str:
    text = _upper(value)
    if not text:
        if optional:
            return ""
        raise Step2ContractError(f"{label} 상태가 비어 있습니다.")
    if text not in allowed:
        raise Step2ContractError(f"{label} 상태 `{value}`는 계약에 없습니다.")
    return text


@dataclass
class Fact:
    fact_id: str
    category: str
    canonical_field: str
    value: Any
    semantic_state: str
    verification_state: str
    sources: list[SourceRef] = field(default_factory=list)
    unit: str = ""
    as_of: str = ""
    confidence: str = ""
    label: str = ""

    def as_matcher_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fact_id": self.fact_id,
            "id": self.fact_id,
            "category": self.category,
            "canonical_field": self.canonical_field,
            "field": self.canonical_field,
            "label": self.label or self.canonical_field,
            "name": self.label or self.canonical_field,
            "value": self.value,
            "semantic_state": self.semantic_state,
            "verification_state": self.verification_state,
            "sources": [source.as_dict() for source in self.sources],
            "unit": self.unit,
            "as_of": self.as_of,
            "confidence": self.confidence,
        }
        if self.sources:
            payload["source_file"] = self.sources[0].source_file
            payload["source_location"] = self.sources[0].source_location
            if self.sources[0].locator:
                payload["locator"] = dict(self.sources[0].locator)
        return payload


@dataclass
class NarrativeEvidence:
    evidence_id: str
    category: str
    text: str
    verification_state: str
    sources: list[SourceRef] = field(default_factory=list)
    semantic_state: str = ""
    name: str = ""

    def as_matcher_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "id": self.evidence_id,
            "category": self.category,
            "text": self.text,
            "verification_state": self.verification_state,
            "semantic_state": self.semantic_state,
            "name": self.name,
            "sources": [source.as_dict() for source in self.sources],
        }
        if self.sources:
            payload["source_file"] = self.sources[0].source_file
            payload["source_location"] = self.sources[0].source_location
            if self.sources[0].locator:
                payload["locator"] = dict(self.sources[0].locator)
        return payload


@dataclass
class Conflict:
    conflict_id: str
    canonical_field: str
    category: str
    candidate_fact_ids: list[str]
    reason: str
    target_section_ids: list[str] = field(default_factory=list)

    def as_matcher_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "id": self.conflict_id,
            "canonical_field": self.canonical_field,
            "field": self.canonical_field,
            "category": self.category,
            "candidate_fact_ids": list(self.candidate_fact_ids),
            "reason": self.reason,
            "target_section_ids": list(self.target_section_ids),
        }


@dataclass
class Step2Output:
    facts: list[Fact]
    narrative_evidence: list[NarrativeEvidence]
    conflicts: list[Conflict]

    def as_matcher_payload(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "facts": [item.as_matcher_dict() for item in self.facts],
            "evidence": [item.as_matcher_dict() for item in self.narrative_evidence],
            "conflicts": [item.as_matcher_dict() for item in self.conflicts],
        }


def parse_step2_output(payload: dict[str, Any]) -> Step2Output:
    """STEP 2 JSON을 검증하고 정규화한다. 입력을 수정하지 않는다."""
    if not isinstance(payload, dict):
        raise Step2ContractError("STEP 2 출력은 object여야 합니다.")

    facts_raw = payload.get("facts")
    if facts_raw is None:
        facts_raw = []
    if not isinstance(facts_raw, list):
        raise Step2ContractError("facts는 array여야 합니다.")

    evidence_raw = payload.get("narrative_evidence")
    if evidence_raw is None:
        evidence_raw = payload.get("evidence")
    if evidence_raw is None:
        evidence_raw = []
    if not isinstance(evidence_raw, list):
        raise Step2ContractError("narrative_evidence는 array여야 합니다.")

    conflicts_raw = payload.get("conflicts")
    if conflicts_raw is None:
        conflicts_raw = []
    if not isinstance(conflicts_raw, list):
        raise Step2ContractError("conflicts는 array여야 합니다.")

    facts: list[Fact] = []
    seen_facts: set[str] = set()
    for index, row in enumerate(facts_raw):
        if not isinstance(row, dict):
            raise Step2ContractError(f"facts[{index}]는 object여야 합니다.")
        fact_id = _text(_first(row, ("fact_id", "id")))
        if not fact_id:
            raise Step2ContractError(f"facts[{index}]에 fact_id가 없습니다. 없는 Fact를 만들지 않습니다.")
        if fact_id in seen_facts:
            raise Step2ContractError(f"fact_id `{fact_id}`가 중복입니다.")
        seen_facts.add(fact_id)
        facts.append(
            Fact(
                fact_id=fact_id,
                category=_upper(row.get("category")),
                canonical_field=_text(_first(row, ("canonical_field", "field", "label", "name"))),
                value=row.get("value"),
                semantic_state=_require_state(
                    row.get("semantic_state"),
                    SEMANTIC_STATES,
                    label=f"{fact_id}.semantic_state",
                    optional=True,
                )
                or "UNKNOWN",
                verification_state=_require_state(
                    row.get("verification_state"),
                    VERIFICATION_STATES,
                    label=f"{fact_id}.verification_state",
                    optional=True,
                )
                or "UNKNOWN",
                sources=_parse_sources(row, label=fact_id),
                unit=_text(row.get("unit")),
                as_of=_text(row.get("as_of")),
                confidence=_text(row.get("confidence")),
                label=_text(_first(row, ("label", "name", "canonical_field", "field"))),
            )
        )

    evidence: list[NarrativeEvidence] = []
    seen_evidence: set[str] = set()
    for index, row in enumerate(evidence_raw):
        if not isinstance(row, dict):
            raise Step2ContractError(f"narrative_evidence[{index}]는 object여야 합니다.")
        evidence_id = _text(_first(row, ("evidence_id", "id")))
        if not evidence_id:
            raise Step2ContractError(
                f"narrative_evidence[{index}]에 evidence_id가 없습니다. 없는 근거를 만들지 않습니다."
            )
        if evidence_id in seen_evidence:
            raise Step2ContractError(f"evidence_id `{evidence_id}`가 중복입니다.")
        seen_evidence.add(evidence_id)
        evidence.append(
            NarrativeEvidence(
                evidence_id=evidence_id,
                category=_upper(row.get("category")),
                text=_text(_first(row, ("text", "summary", "value"))),
                verification_state=_require_state(
                    row.get("verification_state"),
                    VERIFICATION_STATES,
                    label=f"{evidence_id}.verification_state",
                    optional=True,
                )
                or "UNKNOWN",
                sources=_parse_sources(row, label=evidence_id),
                semantic_state=_require_state(
                    row.get("semantic_state"),
                    SEMANTIC_STATES,
                    label=f"{evidence_id}.semantic_state",
                    optional=True,
                ),
                name=_text(_first(row, ("name", "label", "title"))),
            )
        )

    conflicts: list[Conflict] = []
    seen_conflicts: set[str] = set()
    for index, row in enumerate(conflicts_raw):
        if not isinstance(row, dict):
            raise Step2ContractError(f"conflicts[{index}]는 object여야 합니다.")
        conflict_id = _text(_first(row, ("conflict_id", "id")))
        if not conflict_id:
            raise Step2ContractError(f"conflicts[{index}]에 conflict_id가 없습니다.")
        if conflict_id in seen_conflicts:
            raise Step2ContractError(f"conflict_id `{conflict_id}`가 중복입니다.")
        seen_conflicts.add(conflict_id)
        candidates = row.get("candidate_fact_ids") or row.get("fact_ids") or []
        if not isinstance(candidates, list):
            raise Step2ContractError(f"{conflict_id}.candidate_fact_ids는 array여야 합니다.")
        target_ids = row.get("target_section_ids") or []
        if not isinstance(target_ids, list):
            raise Step2ContractError(f"{conflict_id}.target_section_ids는 array여야 합니다.")
        conflicts.append(
            Conflict(
                conflict_id=conflict_id,
                canonical_field=_text(_first(row, ("canonical_field", "field"))),
                category=_upper(row.get("category")),
                candidate_fact_ids=[_text(v) for v in candidates if _text(v)],
                reason=_text(_first(row, ("reason", "description"))),
                target_section_ids=[_text(v) for v in target_ids if _text(v)],
            )
        )

    overlap = seen_facts & seen_evidence
    if overlap:
        raise Step2ContractError(
            "fact_id와 evidence_id가 겹칩니다: " + ", ".join(sorted(overlap))
        )

    known_facts = {item.fact_id for item in facts}
    for conflict in conflicts:
        for fact_id in conflict.candidate_fact_ids:
            if fact_id not in known_facts:
                raise Step2ContractError(
                    f"{conflict.conflict_id}가 없는 fact_id `{fact_id}`를 참조합니다."
                )

    return Step2Output(facts=facts, narrative_evidence=evidence, conflicts=conflicts)
