from __future__ import annotations

from copy import deepcopy

from auto_write.services.section_matcher import match_section, match_sections


def _source() -> dict:
    return {
        "source_file": "기존사업계획서.hwp",
        "source_location": "section 2 / paragraph 3",
    }


def _section(**overrides):
    base = {
        "section_id": "problem",
        "name": "창업아이템 개발 동기 및 필요성",
        "category": "PROBLEM",
    }
    base.update(overrides)
    return base


def _fact(**overrides):
    base = {
        "fact_id": "F-001",
        "category": "REVENUE",
        "canonical_field": "revenue_2025",
        "value": 300_000_000,
        "semantic_state": "ACTUAL",
        "verification_state": "CONFIRMED",
        **_source(),
    }
    base.update(overrides)
    return base


def _evidence(**overrides):
    base = {
        "evidence_id": "E-001",
        "category": "PROBLEM",
        "text": "해외 바이어 발굴에 많은 시간이 소요된다.",
        "verification_state": "CONFIRMED",
        **_source(),
    }
    base.update(overrides)
    return base


def _requirement(**overrides):
    base = {
        "requirement_id": "R-001",
        "name": "시장 문제와 근거",
        "target_section_ids": ["problem"],
        "required": True,
        "blocking": False,
    }
    base.update(overrides)
    return base


def test_problem_evidence_matches_problem_section():
    result = match_section(_section(), [], [_evidence()])

    assert result.matched_evidence_ids == ["E-001"]
    assert result.matched_fact_ids == []
    assert result.writable is True
    assert result.status == "WRITABLE"
    assert result.writable_ko == "현재 자료만으로 작성 가능"


def test_bm_evidence_does_not_match_problem_section_even_with_generic_text_overlap():
    bm = _evidence(
        evidence_id="E-BM",
        category="BUSINESS_MODEL",
        text="사업 문제를 해결한 뒤 월 구독료와 성과형 과금으로 수익을 만든다.",
    )

    result = match_section(_section(), [], [bm])

    assert result.matched_evidence_ids == []
    assert result.writable is False
    assert result.status == "NO_USABLE_MATERIAL"


def test_actual_requirement_does_not_accept_plan_revenue_fact():
    section = _section(
        section_id="revenue",
        name="매출 실적 및 계획",
        category="REVENUE",
    )
    plan_fact = _fact(
        fact_id="F-PLAN",
        canonical_field="revenue_2025",
        value=300_000_000,
        semantic_state="PLAN",
    )
    requirement = _requirement(
        requirement_id="R-ACTUAL",
        name="2025년 실제 매출",
        target_section_ids=["revenue"],
        required_field="revenue_2025",
        semantic_state="ACTUAL",
        material_type="FACT",
        blocking=True,
    )

    result = match_section(section, [plan_fact], [], [requirement])

    assert result.matched_fact_ids == ["F-PLAN"]
    assert result.satisfied_requirement_ids == []
    assert [m.requirement_id for m in result.missing_requirements] == ["R-ACTUAL"]
    assert result.missing_requirements[0].reason_code == "MISSING_SEMANTIC_STATE"
    assert result.writable is False
    assert result.status == "BLOCKED_REQUIRED_INFO"
    assert "ACTUAL" in result.missing_requirements[0].reason_ko


def test_conflict_fact_is_never_auto_selected_and_conflict_is_surfaced():
    section = _section(
        section_id="pricing",
        name="가격 및 수익모델",
        category="BUSINESS_MODEL",
    )
    conflict_fact = _fact(
        fact_id="F-PRICE",
        category="BUSINESS_MODEL",
        canonical_field="buyer_flow_total",
        value="100,000원",
        semantic_state="ACTUAL",
        verification_state="CONFLICT",
    )
    conflicts = [
        {
            "conflict_id": "C-PRICE",
            "category": "BUSINESS_MODEL",
            "canonical_field": "buyer_flow_total",
            "reason": "문서 버전별 가격 불일치",
        }
    ]

    result = match_section(section, [conflict_fact], [], conflicts=conflicts)

    assert result.matched_fact_ids == []
    assert [row.material_id for row in result.unusable_materials] == ["F-PRICE"]
    assert result.unusable_materials[0].reason_code == "BLOCKED_STATE"
    assert [row["conflict_id"] for row in result.conflicts] == ["C-PRICE"]
    assert result.writable is False


def test_material_without_source_location_is_not_usable():
    no_locator = _evidence(source_location="")

    result = match_section(_section(), [], [no_locator])

    assert result.matched_evidence_ids == []
    assert result.unusable_materials[0].reason_code == "NO_SOURCE"
    assert "출처" in result.unusable_materials[0].reason_ko
    assert result.writable is False


def test_partial_material_can_be_writable_with_nonblocking_missing_requirement():
    requirement = _requirement(
        requirement_id="R-INTERVIEW",
        name="고객 인터뷰 실적",
        required_field="customer_interview_count",
        material_type="FACT",
        blocking=False,
    )

    result = match_section(_section(), [], [_evidence()], [requirement])

    assert result.matched_evidence_ids == ["E-001"]
    assert [m.requirement_id for m in result.missing_requirements] == ["R-INTERVIEW"]
    assert result.missing_requirements[0].blocking is False
    assert result.writable is True
    assert result.status == "PARTIAL_WRITABLE"
    assert result.writable_ko == "일부 정보가 부족하지만 현재 자료로 작성 가능"
    assert "부족한 정보 1개" in result.reason_ko


def test_blocking_missing_requirement_makes_section_not_writable():
    requirement = _requirement(
        requirement_id="R-REQUIRED",
        name="반드시 필요한 검증 실적",
        required_field="validation_count",
        material_type="FACT",
        blocking=True,
    )

    result = match_section(_section(), [], [_evidence()], [requirement])

    assert result.writable is False
    assert result.status == "BLOCKED_REQUIRED_INFO"
    assert result.writable_ko == "필수 정보가 부족해 작성 보류"
    assert "반드시 필요한 검증 실적" in result.reason_ko


def test_program_requirement_can_target_section_id_directly():
    requirement = _requirement(
        requirement_id="R-DIRECT",
        name="바이어 발굴 문제",
        target_section_ids=["problem"],
        material_type="EVIDENCE",
    )

    result = match_section(_section(), [], [_evidence()], [requirement])

    assert result.program_requirement_ids == ["R-DIRECT"]
    assert result.satisfied_requirement_ids == ["R-DIRECT"]
    assert result.missing_requirements == []


def test_required_field_is_satisfied_only_by_exact_canonical_field():
    section = _section(section_id="revenue", name="매출 계획", category="REVENUE")
    wrong = _fact(fact_id="F-WRONG", canonical_field="revenue_2024")
    requirement = _requirement(
        requirement_id="R-2025",
        target_section_ids=["revenue"],
        required_field="revenue_2025",
        semantic_state="ACTUAL",
        material_type="FACT",
        blocking=True,
    )

    wrong_result = match_section(section, [wrong], [], [requirement])
    right_result = match_section(section, [wrong, _fact(fact_id="F-RIGHT")], [], [requirement])

    assert wrong_result.satisfied_requirement_ids == []
    assert wrong_result.writable is False
    assert right_result.satisfied_requirement_ids == ["R-2025"]
    assert right_result.writable is True


def test_multiple_source_material_ids_are_preserved_without_collapsing_provenance():
    e1 = _evidence(evidence_id="E-D1", source_file="D1.hwp", source_location="section 2")
    e2 = _evidence(evidence_id="E-D2", source_file="D2.hwp", source_location="page 4")

    result = match_section(_section(), [], [e1, e2])

    assert result.matched_evidence_ids == ["E-D1", "E-D2"]
    assert result.writable is True


def test_explicit_section_semantic_state_filters_incompatible_material():
    section = _section(
        section_id="revenue_actual",
        name="최근 매출 실적",
        category="REVENUE",
        semantic_state="ACTUAL",
    )
    plan = _fact(fact_id="F-PLAN", semantic_state="PLAN")
    actual = _fact(fact_id="F-ACTUAL", semantic_state="ACTUAL")

    result = match_section(section, [plan, actual], [])

    assert result.matched_fact_ids == ["F-ACTUAL"]
    assert [u.material_id for u in result.unusable_materials] == ["F-PLAN"]
    assert result.unusable_materials[0].reason_code == "SEMANTIC_MISMATCH"


def test_unknown_fact_does_not_become_zero_or_not_applicable():
    unknown = _fact(
        fact_id="F-UNKNOWN",
        category="PROBLEM",
        canonical_field="customer_interview_count",
        value="0",
        verification_state="UNKNOWN",
    )

    result = match_section(_section(), [unknown], [])

    assert result.matched_fact_ids == []
    assert result.unusable_materials[0].reason_code == "BLOCKED_STATE"
    assert result.writable is False


def test_not_applicable_fact_is_not_treated_as_unknown_when_explicitly_usable():
    fact = _fact(
        fact_id="F-NA",
        category="PROBLEM",
        canonical_field="offline_store_count",
        value="해당 없음",
        verification_state="NOT_APPLICABLE",
    )

    result = match_section(_section(), [fact], [])

    assert result.matched_fact_ids == ["F-NA"]
    assert result.writable is True


def test_locator_dict_counts_as_real_source_location():
    evidence = _evidence(source_location="", locator={"page": 3, "block": 7})

    result = match_section(_section(), [], [evidence])

    assert result.matched_evidence_ids == ["E-001"]
    assert result.writable is True


def test_match_sections_is_deterministic_and_does_not_mutate_inputs():
    sections = [
        _section(),
        _section(section_id="team", name="대표자 및 팀 역량", category="TEAM"),
    ]
    facts = [
        _fact(fact_id="F-TEAM", category="TEAM", canonical_field="founder_experience", value="Tax 3년 8개월"),
    ]
    evidence = [_evidence()]
    requirements = [_requirement()]
    conflicts = []
    before = deepcopy((sections, facts, evidence, requirements, conflicts))

    first = match_sections(sections, facts, evidence, requirements, conflicts)
    second = match_sections(sections, facts, evidence, requirements, conflicts)

    assert [row.as_dict() for row in first] == [row.as_dict() for row in second]
    assert (sections, facts, evidence, requirements, conflicts) == before
    assert first[0].target_section_id == "problem"
    assert first[1].target_section_id == "team"
