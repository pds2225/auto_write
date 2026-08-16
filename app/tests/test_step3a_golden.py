"""STEP 3A Golden: 양식 항목 ↔ Fact/Evidence ↔ 공고 요구사항.

Writer / UI / HWP / STEP 2 추출기를 호출하지 않는다.
입력은 합성 STEP 2 JSON이다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from auto_write.services.section_matcher import (
    format_human_report,
    match_from_step2,
    match_section,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "step3a"
REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "app" / "tools" / "step3a_section_match.py"


def _source(**overrides) -> dict:
    base = {
        "source_file": "기존사업계획서.hwp",
        "source_location": "section 2 / paragraph 3",
    }
    base.update(overrides)
    return base


def _problem_section(**overrides) -> dict:
    base = {
        "section_id": "problem",
        "name": "문제인식",
        "category": "PROBLEM",
    }
    base.update(overrides)
    return base


def _fact(**overrides) -> dict:
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


def _evidence(**overrides) -> dict:
    base = {
        "evidence_id": "E-001",
        "category": "PROBLEM",
        "text": "해외 바이어 발굴에 많은 시간이 소요된다.",
        "verification_state": "CONFIRMED",
        **_source(),
    }
    base.update(overrides)
    return base


def test_golden_problem_evidence_sufficient_matches_problem() -> None:
    result = match_section(_problem_section(), [], [_evidence()])

    assert result.matched_evidence_ids == ["E-001"]
    assert result.writable is True
    assert result.status == "WRITABLE"


def test_golden_bm_evidence_in_problem_fails() -> None:
    bm = _evidence(
        evidence_id="E-BM",
        category="BUSINESS_MODEL",
        text="사업 문제를 해결한 뒤 월 구독료로 수익을 만든다.",
    )
    result = match_section(_problem_section(), [], [bm])

    assert result.matched_evidence_ids == []
    assert result.writable is False
    assert result.status == "NO_USABLE_MATERIAL"


def test_golden_plan_revenue_not_used_as_actual_fails() -> None:
    section = {
        "section_id": "revenue",
        "name": "매출 실적",
        "category": "REVENUE",
        "semantic_state": "ACTUAL",
    }
    plan = _fact(fact_id="F-PLAN", semantic_state="PLAN")
    result = match_section(section, [plan], [])

    assert result.matched_fact_ids == []
    assert result.unusable_materials[0].reason_code == "SEMANTIC_MISMATCH"
    assert result.writable is False


def test_golden_conflict_fact_not_auto_selected_fails() -> None:
    fact = _fact(
        fact_id="F-PRICE",
        category="PROBLEM",
        verification_state="CONFLICT",
    )
    result = match_section(_problem_section(), [fact], [])

    assert result.matched_fact_ids == []
    assert result.unusable_materials[0].reason_code == "BLOCKED_STATE"
    assert result.writable is False


def test_golden_missing_fact_is_not_invented_fails() -> None:
    result = match_section(_problem_section(), [], [_evidence()])

    assert "F-GENERATED" not in result.matched_fact_ids
    assert set(result.matched_fact_ids) <= set()
    empty = match_section(_problem_section(), [], [])
    assert empty.matched_fact_ids == []
    assert empty.matched_evidence_ids == []


def test_golden_partial_evidence_is_writable_with_missing_label() -> None:
    requirement = {
        "requirement_id": "R-INTERVIEW",
        "name": "고객 인터뷰 결과",
        "target_section_ids": ["problem"],
        "required": True,
        "blocking": False,
        "required_field": "customer_interview_count",
        "material_type": "FACT",
    }
    result = match_section(_problem_section(), [], [_evidence()], [requirement])

    assert result.writable is True
    assert result.status == "PARTIAL_WRITABLE"
    assert [item.name for item in result.missing_requirements] == ["고객 인터뷰 결과"]


def test_golden_evidence_without_source_is_unusable() -> None:
    result = match_section(_problem_section(), [], [_evidence(source_file="", source_location="")])

    assert result.matched_evidence_ids == []
    assert result.unusable_materials[0].reason_code == "NO_SOURCE"
    assert result.writable is False


def test_golden_one_fact_keeps_multiple_sources_in_provenance() -> None:
    fact = _fact(
        fact_id="F-MULTI",
        category="PROBLEM",
        canonical_field="pain_count",
        value="월 120건",
        sources=[
            {"source_file": "D1.hwp", "source_location": "p.2"},
            {"source_file": "D2.hwp", "source_location": "표1"},
        ],
    )
    result = match_section(_problem_section(), [fact], [])

    assert result.matched_fact_ids == ["F-MULTI"]
    assert result.matched_provenance[0]["sources"] == [
        {"source_file": "D1.hwp", "source_location": "p.2"},
        {"source_file": "D2.hwp", "source_location": "표1"},
    ]


def test_human_report_matches_nondev_example() -> None:
    bundle = json.loads((FIXTURE_DIR / "writable_problem_bundle.json").read_text(encoding="utf-8"))
    expected = (FIXTURE_DIR / "writable_problem_report.txt").read_text(encoding="utf-8")
    matches = match_from_step2(bundle["sections"], bundle["step2"], bundle["requirements"])
    assert format_human_report(matches) == expected
    assert matches[0].writable is True
    assert len(matches[0].matched_evidence_ids) == 4
    assert [item.name for item in matches[0].missing_requirements] == ["고객 인터뷰 결과"]


def test_cli_prints_same_human_report() -> None:
    expected = (FIXTURE_DIR / "writable_problem_report.txt").read_text(encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CLI), "--bundle", str(FIXTURE_DIR / "writable_problem_bundle.json")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == expected


def test_match_from_step2_never_adds_fact_ids_outside_input() -> None:
    bundle = json.loads((FIXTURE_DIR / "writable_problem_bundle.json").read_text(encoding="utf-8"))
    input_fact_ids = {row["fact_id"] for row in bundle["step2"]["facts"]}
    input_evidence_ids = {row["evidence_id"] for row in bundle["step2"]["narrative_evidence"]}
    matches = match_from_step2(bundle["sections"], bundle["step2"], bundle["requirements"])
    for match in matches:
        assert set(match.matched_fact_ids) <= input_fact_ids
        assert set(match.matched_evidence_ids) <= input_evidence_ids
