"""STEP 3A: structured section matching contract.

STEP 2가 추출한 Fact / Narrative Evidence를 이번 양식의 섹션과 공고 요구사항에
연결하는 결정론적 matcher다. 이 모듈은 글을 쓰지 않는다.

중요 불변:
- 없는 Fact/Evidence를 만들지 않는다.
- ACTUAL/PLAN 등 의미 상태를 요구사항과 맞춰 사용한다.
- CONFLICT/UNKNOWN/STALE/REVIEW_REQUIRED/UNVERIFIABLE 자료를 자동 선택하지 않는다.
- source_file + source_location(또는 locator)이 없는 근거는 사용하지 않는다.
- 일부 정보가 부족해도 쓸 근거가 있으면 writable=True가 될 수 있다.
- blocking 요구사항이 빠지면 writable=False다.

내부 코드는 영어 식별자를 쓰되, 사람이 보는 상태/이유는 한글을 함께 반환한다.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .step2_output_contract import Step2Output, parse_step2_output


STATUS_KO = {
    "WRITABLE": "현재 자료만으로 작성 가능",
    "PARTIAL_WRITABLE": "일부 정보가 부족하지만 현재 자료로 작성 가능",
    "BLOCKED_REQUIRED_INFO": "필수 정보가 부족해 작성 보류",
    "NO_USABLE_MATERIAL": "사용할 수 있는 근거가 없어 작성 보류",
}

HUMAN_STATUS_KO = {
    "WRITABLE": "작성 가능",
    "PARTIAL_WRITABLE": "작성 가능",
    "BLOCKED_REQUIRED_INFO": "작성 보류",
    "NO_USABLE_MATERIAL": "작성 보류",
}

UNUSABLE_REASON_KO = {
    "EMPTY": "값 또는 서술 내용이 비어 있음",
    "NO_SOURCE": "출처 파일 또는 원문 위치가 없음",
    "BLOCKED_STATE": "확정해서 쓰면 안 되는 상태",
    "SEMANTIC_MISMATCH": "요구된 의미 상태와 맞지 않음",
}

_BLOCKED_STATES = {
    "UNKNOWN",
    "CONFLICT",
    "INTERNAL_CONFLICT",
    "STALE",
    "UNVERIFIABLE",
    "REVIEW_REQUIRED",
}

# 카테고리 추론은 명시 category가 없을 때만 쓰는 보조 수단이다.
# 짧고 일반적인 단어보다 사업계획서에서 의미가 분명한 표현을 우선한다.
_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "COMPANY": ("기업개요", "기업 개요", "기업현황", "기업 현황", "회사개요", "회사 개요"),
    "ITEM": ("창업아이템", "창업 아이템", "아이템 개요", "제품 개요", "서비스 개요"),
    "PROBLEM": ("문제인식", "문제 인식", "문제정의", "문제 정의", "개발 동기", "필요성"),
    "SOLUTION": ("해결방안", "해결 방안", "실현가능성", "실현 가능성", "솔루션", "개발방안"),
    "MARKET": ("시장규모", "시장 규모", "시장분석", "시장 분석", "목표시장", "목표 시장"),
    "CUSTOMER": ("목표고객", "목표 고객", "타깃고객", "타깃 고객", "고객군"),
    "DIFFERENTIATION": ("차별성", "차별화", "경쟁력", "경쟁우위", "경쟁 우위", "경쟁사"),
    "BUSINESS_MODEL": ("비즈니스모델", "비즈니스 모델", "수익모델", "수익 모델", "수익구조", "수익 구조"),
    "TRACTION": ("사업실적", "사업 실적", "주요실적", "주요 실적", "고객확보", "고객 확보", "검증실적"),
    "TEAM": ("팀 구성", "팀구성", "팀 역량", "팀역량", "대표자 역량", "인력 구성"),
    "REVENUE": ("매출실적", "매출 실적", "매출계획", "매출 계획", "매출액"),
    "FINANCE": ("재무현황", "재무 현황", "재무계획", "재무 계획", "손익계획", "손익 계획"),
    "FUNDING": ("자금조달", "자금 조달", "사업비", "소요자금", "소요 자금"),
    "DEVELOPMENT": ("개발현황", "개발 현황", "개발단계", "개발 단계", "개발계획", "개발 계획"),
    "DATA": ("데이터 보유", "데이터 구축", "데이터 현황", "데이터 규모"),
    "GROWTH": ("성장전략", "성장 전략", "성장계획", "성장 계획", "스케일업", "scale-up"),
    "SCHEDULE": ("추진일정", "추진 일정", "사업일정", "사업 일정", "로드맵"),
    "IP": ("지식재산", "지식 재산", "특허", "상표권", "저작권"),
    "PARTNERS": ("협력기관", "협력 기관", "협력사", "파트너", "네트워크"),
}

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_GENERIC_TOKENS = {
    "작성", "내용", "계획", "현황", "관련", "사업", "지원", "항목", "기타",
    "the", "and", "for", "with",
}


@dataclass(frozen=True)
class MissingRequirement:
    requirement_id: str
    name: str
    blocking: bool
    reason_code: str
    reason_ko: str


@dataclass(frozen=True)
class UnusableMaterial:
    material_id: str
    material_type: str
    reason_code: str
    reason_ko: str


@dataclass
class SectionMatch:
    target_section_id: str
    target_section_name: str
    matched_fact_ids: list[str] = field(default_factory=list)
    matched_evidence_ids: list[str] = field(default_factory=list)
    program_requirement_ids: list[str] = field(default_factory=list)
    satisfied_requirement_ids: list[str] = field(default_factory=list)
    missing_requirements: list[MissingRequirement] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    unusable_materials: list[UnusableMaterial] = field(default_factory=list)
    matched_provenance: list[dict[str, Any]] = field(default_factory=list)
    writable: bool = False
    status: str = "NO_USABLE_MATERIAL"
    writable_ko: str = STATUS_KO["NO_USABLE_MATERIAL"]
    reason_ko: str = "사용할 수 있는 근거가 없습니다."

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def _id_of(item: dict[str, Any], kind: str) -> str:
    if kind == "section":
        keys = ("section_id", "question_id", "field_id", "id")
    elif kind == "fact":
        keys = ("fact_id", "id")
    elif kind == "evidence":
        keys = ("evidence_id", "id")
    elif kind == "requirement":
        keys = ("requirement_id", "id")
    else:
        keys = ("conflict_id", "id")
    return _text(_first(item, keys))


def _name_of(item: dict[str, Any]) -> str:
    return _text(_first(item, ("name", "label", "title", "description")))


def _tokens(*values: Any) -> set[str]:
    out: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            text = " ".join(_text(v) for v in value)
        else:
            text = _text(value)
        for token in _TOKEN_RE.findall(text.lower()):
            if token not in _GENERIC_TOKENS:
                out.add(token)
    return out


def _explicit_categories(item: dict[str, Any]) -> set[str]:
    raw: list[Any] = []
    if item.get("category") not in (None, ""):
        raw.append(item.get("category"))
    categories = item.get("categories")
    if isinstance(categories, (list, tuple, set)):
        raw.extend(categories)
    elif categories not in (None, ""):
        raw.append(categories)
    return {_upper(value) for value in raw if _text(value)}


def _infer_categories(*values: Any) -> set[str]:
    combined = " ".join(
        " ".join(_text(v) for v in value) if isinstance(value, (list, tuple, set)) else _text(value)
        for value in values
    ).lower()
    found: set[str] = set()
    for category, aliases in _CATEGORY_ALIASES.items():
        if any(alias.lower() in combined for alias in aliases):
            found.add(category)
    return found


def _categories_of(item: dict[str, Any], *, infer_from: tuple[str, ...]) -> set[str]:
    explicit = _explicit_categories(item)
    if explicit:
        return explicit
    values = [item.get(key) for key in infer_from]
    return _infer_categories(*values)


def _section_categories(section: dict[str, Any]) -> set[str]:
    return _categories_of(
        section,
        infer_from=("name", "label", "title", "description", "source_hint", "keywords"),
    )


def _material_categories(material: dict[str, Any], material_type: str) -> set[str]:
    fields = ("canonical_field", "field", "name", "label", "text", "value")
    if material_type == "EVIDENCE":
        fields = ("name", "label", "title", "text", "summary")
    return _categories_of(material, infer_from=fields)


def _requirement_categories(requirement: dict[str, Any]) -> set[str]:
    return _categories_of(
        requirement,
        infer_from=("name", "label", "title", "description", "keywords", "required_field"),
    )


def _source_location(material: dict[str, Any]) -> str:
    direct = _text(_first(material, ("source_location", "location")))
    if direct:
        return direct
    locator = material.get("locator")
    if isinstance(locator, dict) and locator:
        return "locator"
    if isinstance(locator, str) and locator.strip():
        return locator.strip()
    return ""


def _iter_sources(material: dict[str, Any]) -> list[dict[str, Any]]:
    raw = material.get("sources")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        rows.extend(row for row in raw if isinstance(row, dict))
    if not rows:
        rows.append(material)
    return rows


def _material_sources(material: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in _iter_sources(material):
        source_file = _text(row.get("source_file"))
        location = _source_location(row)
        if not source_file and not location:
            continue
        key = (source_file, location)
        if key in seen:
            continue
        seen.add(key)
        item: dict[str, Any] = {
            "source_file": source_file,
            "source_location": location,
        }
        locator = row.get("locator")
        if isinstance(locator, dict) and locator:
            item["locator"] = dict(locator)
        sources.append(item)
    return sources


def _has_provenance(material: dict[str, Any]) -> bool:
    return any(
        _text(row.get("source_file")) and _source_location(row)
        for row in _iter_sources(material)
    )


def _material_value(material: dict[str, Any], material_type: str) -> str:
    if material_type == "FACT":
        return _text(_first(material, ("value", "raw_value")))
    return _text(_first(material, ("text", "summary", "value")))


def _material_state(material: dict[str, Any]) -> tuple[str, str]:
    verification = _upper(material.get("verification_state"))
    semantic = _upper(material.get("semantic_state"))
    return verification, semantic


def _blocked(material: dict[str, Any]) -> bool:
    verification, semantic = _material_state(material)
    if verification in _BLOCKED_STATES or semantic in _BLOCKED_STATES:
        return True
    # 구현에 따라 `CONFLICT:...` 같은 세부 상태가 들어와도 자동 선택하지 않는다.
    return any(
        state.startswith(prefix)
        for state in (verification, semantic)
        for prefix in ("CONFLICT_", "INTERNAL_CONFLICT_", "STALE_")
    )


def _semantic_allowed(material: dict[str, Any], expected_states: set[str]) -> bool:
    if not expected_states:
        return True
    semantic = _upper(material.get("semantic_state"))
    return bool(semantic and semantic in expected_states)


def _section_expected_states(section: dict[str, Any]) -> set[str]:
    raw = section.get("semantic_states")
    states: list[Any] = []
    if isinstance(raw, (list, tuple, set)):
        states.extend(raw)
    elif raw not in (None, ""):
        states.append(raw)
    if section.get("semantic_state") not in (None, ""):
        states.append(section.get("semantic_state"))
    return {_upper(v) for v in states if _text(v)}


def _field_of(material: dict[str, Any]) -> str:
    return _text(_first(material, ("canonical_field", "field")))


def _match_strength(
    section: dict[str, Any],
    material: dict[str, Any],
    *,
    material_type: str,
) -> int:
    section_categories = _section_categories(section)
    material_categories = _material_categories(material, material_type)

    if section_categories and material_categories:
        if section_categories & material_categories:
            return 100
        # 명시적으로 서로 다른 카테고리는 텍스트 우연일치로 뒤집지 않는다.
        return 0

    section_tokens = _tokens(
        _name_of(section),
        section.get("description"),
        section.get("source_hint"),
        section.get("keywords"),
    )
    material_tokens = _tokens(
        _name_of(material),
        _field_of(material),
        material.get("text"),
    )
    overlap = section_tokens & material_tokens
    if not overlap:
        return 0
    return 10 + min(len(overlap), 5)


def _unusable_reason(material: dict[str, Any], material_type: str) -> tuple[str, str] | None:
    if not _material_value(material, material_type):
        return "EMPTY", UNUSABLE_REASON_KO["EMPTY"]
    if not _has_provenance(material):
        return "NO_SOURCE", UNUSABLE_REASON_KO["NO_SOURCE"]
    if _blocked(material):
        return "BLOCKED_STATE", UNUSABLE_REASON_KO["BLOCKED_STATE"]
    return None


def _requirement_target_ids(requirement: dict[str, Any]) -> set[str]:
    raw = requirement.get("target_section_ids")
    if isinstance(raw, (list, tuple, set)):
        return {_text(v) for v in raw if _text(v)}
    if raw not in (None, ""):
        return {_text(raw)}
    direct = _text(requirement.get("target_section_id")) or _text(requirement.get("section_id"))
    return {direct} if direct else set()


def _requirement_applies(requirement: dict[str, Any], section: dict[str, Any]) -> bool:
    section_id = _id_of(section, "section")
    target_ids = _requirement_target_ids(requirement)
    if target_ids:
        return section_id in target_ids

    req_categories = _requirement_categories(requirement)
    sec_categories = _section_categories(section)
    if req_categories and sec_categories:
        return bool(req_categories & sec_categories)

    req_tokens = _tokens(
        _name_of(requirement),
        requirement.get("description"),
        requirement.get("keywords"),
    )
    sec_tokens = _tokens(
        _name_of(section),
        section.get("description"),
        section.get("source_hint"),
        section.get("keywords"),
    )
    return bool(req_tokens & sec_tokens)


def _expected_semantic_states(requirement: dict[str, Any]) -> set[str]:
    raw = requirement.get("semantic_states")
    states: list[Any] = []
    if isinstance(raw, (list, tuple, set)):
        states.extend(raw)
    elif raw not in (None, ""):
        states.append(raw)
    if requirement.get("semantic_state") not in (None, ""):
        states.append(requirement.get("semantic_state"))
    return {_upper(v) for v in states if _text(v)}


def _material_type_requirement(requirement: dict[str, Any]) -> str:
    value = _upper(requirement.get("material_type"))
    return value if value in {"FACT", "EVIDENCE"} else ""


def _requirement_satisfied(
    requirement: dict[str, Any],
    matched_facts: list[dict[str, Any]],
    matched_evidence: list[dict[str, Any]],
) -> bool:
    expected_states = _expected_semantic_states(requirement)
    required_field = _text(requirement.get("required_field"))
    expected_type = _material_type_requirement(requirement)
    req_categories = _requirement_categories(requirement)
    req_tokens = _tokens(
        _name_of(requirement),
        requirement.get("description"),
        requirement.get("keywords"),
    )

    candidates: list[tuple[str, dict[str, Any]]] = []
    if expected_type in {"", "FACT"}:
        candidates.extend(("FACT", fact) for fact in matched_facts)
    if expected_type in {"", "EVIDENCE"}:
        candidates.extend(("EVIDENCE", ev) for ev in matched_evidence)

    for material_type, material in candidates:
        if not _semantic_allowed(material, expected_states):
            continue
        if required_field:
            if material_type != "FACT" or _field_of(material) != required_field:
                continue
            return True

        material_categories = _material_categories(material, material_type)
        if req_categories and material_categories:
            if req_categories & material_categories:
                return True
            continue

        if req_tokens:
            material_tokens = _tokens(
                _name_of(material),
                _field_of(material),
                material.get("text"),
            )
            if req_tokens & material_tokens:
                return True
        elif not req_categories:
            # target_section_ids만으로 적용된 단순 요구사항은 해당 섹션에 근거가 하나라도 있으면 충족.
            return True
    return False


def _conflict_applies(conflict: dict[str, Any], section: dict[str, Any]) -> bool:
    section_id = _id_of(section, "section")
    targets = _requirement_target_ids(conflict)
    if targets:
        return section_id in targets

    conflict_categories = _categories_of(
        conflict,
        infer_from=("field", "canonical_field", "name", "reason", "description"),
    )
    section_categories = _section_categories(section)
    if conflict_categories and section_categories:
        return bool(conflict_categories & section_categories)

    field_name = _field_of(conflict)
    if field_name:
        section_tokens = _tokens(_name_of(section), section.get("keywords"), section.get("description"))
        return bool(section_tokens & _tokens(field_name))
    return False


def _append_unusable(
    output: list[UnusableMaterial],
    material_id: str,
    material_type: str,
    reason_code: str,
    reason_ko: str,
) -> None:
    key = (material_id, material_type, reason_code)
    if any((row.material_id, row.material_type, row.reason_code) == key for row in output):
        return
    output.append(UnusableMaterial(material_id, material_type, reason_code, reason_ko))


def match_section(
    section: dict[str, Any],
    facts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    requirements: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
) -> SectionMatch:
    """한 양식 섹션에 사용할 기존 자료와 부족정보를 결정론적으로 연결한다."""
    section_id = _id_of(section, "section")
    if not section_id:
        raise ValueError("section에는 section_id/question_id/field_id/id 중 하나가 필요합니다.")
    section_name = _name_of(section) or section_id
    expected_states = _section_expected_states(section)

    matched_facts: list[dict[str, Any]] = []
    matched_evidence: list[dict[str, Any]] = []
    unusable: list[UnusableMaterial] = []

    for material_type, items, matched in (
        ("FACT", facts, matched_facts),
        ("EVIDENCE", evidence, matched_evidence),
    ):
        for material in items:
            material_id = _id_of(material, "fact" if material_type == "FACT" else "evidence")
            if not material_id:
                continue
            if _match_strength(section, material, material_type=material_type) <= 0:
                continue
            reason = _unusable_reason(material, material_type)
            if reason:
                _append_unusable(unusable, material_id, material_type, reason[0], reason[1])
                continue
            if expected_states and not _semantic_allowed(material, expected_states):
                _append_unusable(
                    unusable,
                    material_id,
                    material_type,
                    "SEMANTIC_MISMATCH",
                    UNUSABLE_REASON_KO["SEMANTIC_MISMATCH"],
                )
                continue
            matched.append(material)

    matched_provenance = [
        {
            "material_id": _id_of(item, "fact"),
            "material_type": "FACT",
            "sources": _material_sources(item),
        }
        for item in matched_facts
    ]
    matched_provenance.extend(
        {
            "material_id": _id_of(item, "evidence"),
            "material_type": "EVIDENCE",
            "sources": _material_sources(item),
        }
        for item in matched_evidence
    )
    applicable_requirements = [
        requirement
        for requirement in (requirements or [])
        if _requirement_applies(requirement, section)
    ]
    requirement_ids: list[str] = []
    satisfied_ids: list[str] = []
    missing: list[MissingRequirement] = []

    for requirement in applicable_requirements:
        requirement_id = _id_of(requirement, "requirement")
        if not requirement_id:
            continue
        requirement_ids.append(requirement_id)
        if _requirement_satisfied(requirement, matched_facts, matched_evidence):
            satisfied_ids.append(requirement_id)
            continue
        if bool(requirement.get("required", True)):
            name = _name_of(requirement) or requirement_id
            blocking = bool(requirement.get("blocking", False))
            expected = _expected_semantic_states(requirement)
            reason_code = "MISSING_REQUIRED_MATERIAL"
            reason_ko = "요구사항을 충족하는 근거가 없음"
            if expected:
                reason_code = "MISSING_SEMANTIC_STATE"
                reason_ko = f"요구된 의미 상태({', '.join(sorted(expected))})의 근거가 없음"
            missing.append(
                MissingRequirement(
                    requirement_id=requirement_id,
                    name=name,
                    blocking=blocking,
                    reason_code=reason_code,
                    reason_ko=reason_ko,
                )
            )

    section_conflicts = [
        dict(conflict)
        for conflict in (conflicts or [])
        if _conflict_applies(conflict, section)
    ]

    matched_fact_ids = [_id_of(item, "fact") for item in matched_facts]
    matched_evidence_ids = [_id_of(item, "evidence") for item in matched_evidence]
    has_material = bool(matched_fact_ids or matched_evidence_ids)
    blocking_missing = any(item.blocking for item in missing)

    if blocking_missing:
        status = "BLOCKED_REQUIRED_INFO"
        writable = False
        blocked_names = ", ".join(item.name for item in missing if item.blocking)
        reason_ko = f"필수 정보가 부족합니다: {blocked_names}"
    elif not has_material:
        status = "NO_USABLE_MATERIAL"
        writable = False
        reason_ko = "출처가 확인된 사용 가능 근거가 없습니다."
    elif missing or section_conflicts:
        status = "PARTIAL_WRITABLE"
        writable = True
        pieces = [f"사용 가능한 근거 {len(matched_fact_ids) + len(matched_evidence_ids)}개"]
        if missing:
            pieces.append(f"부족한 정보 {len(missing)}개")
        if section_conflicts:
            pieces.append(f"확인할 충돌 {len(section_conflicts)}개")
        reason_ko = ", ".join(pieces) + ". 현재 근거 범위에서 작성할 수 있습니다."
    else:
        status = "WRITABLE"
        writable = True
        reason_ko = f"출처가 확인된 근거 {len(matched_fact_ids) + len(matched_evidence_ids)}개로 작성할 수 있습니다."

    return SectionMatch(
        target_section_id=section_id,
        target_section_name=section_name,
        matched_fact_ids=matched_fact_ids,
        matched_evidence_ids=matched_evidence_ids,
        program_requirement_ids=requirement_ids,
        satisfied_requirement_ids=satisfied_ids,
        missing_requirements=missing,
        conflicts=section_conflicts,
        unusable_materials=unusable,
        matched_provenance=matched_provenance,
        writable=writable,
        status=status,
        writable_ko=STATUS_KO[status],
        reason_ko=reason_ko,
    )


def match_sections(
    sections: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    requirements: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
) -> list[SectionMatch]:
    """여러 양식 섹션을 매칭한다. 입력 객체는 수정하지 않는다."""
    return [
        match_section(section, facts, evidence, requirements, conflicts)
        for section in sections
    ]


def match_from_step2(
    sections: list[dict[str, Any]],
    step2: dict[str, Any] | Step2Output,
    requirements: list[dict[str, Any]] | None = None,
) -> list[SectionMatch]:
    """검증된 STEP 2 출력만 받아 섹션 매칭한다. 추출기를 호출하지 않는다."""
    parsed = step2 if isinstance(step2, Step2Output) else parse_step2_output(step2)
    payload = parsed.as_matcher_payload()
    return match_sections(
        sections,
        payload["facts"],
        payload["evidence"],
        requirements,
        payload["conflicts"],
    )


def format_human_report(matches: list[SectionMatch]) -> str:
    """비개발자용 한글 리포트. Writer 초안이 아니라 작성 가능/부족정보만 보여 준다."""
    blocks: list[str] = []
    for match in matches:
        lines = [
            f"{match.target_section_name} — {HUMAN_STATUS_KO.get(match.status, match.status)}"
        ]
        usable = len(match.matched_fact_ids) + len(match.matched_evidence_ids)
        if usable:
            lines.append(f"사용 가능한 근거 {usable}개")
        if match.missing_requirements:
            names = ", ".join(item.name for item in match.missing_requirements)
            lines.append(f"부족한 정보 {len(match.missing_requirements)}개: {names}")
        if match.conflicts:
            lines.append(f"확인할 충돌 {len(match.conflicts)}개")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")
