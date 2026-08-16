"""STEP 2 Output Contract — STEP 3A matcher 입력 형식.

추출기 구현이 아니라 Fact[] / NarrativeEvidence[] / Conflict[] 계약만 검증한다.
"""
from __future__ import annotations

import pytest

from auto_write.services.step2_output_contract import (
    Step2ContractError,
    parse_step2_output,
)


def test_parse_accepts_sources_array_and_legacy_source_file() -> None:
    parsed = parse_step2_output(
        {
            "facts": [
                {
                    "fact_id": "f1",
                    "label": "대표자",
                    "value": "홍길동",
                    "category": "company",
                    "semantic_state": "ACTUAL",
                    "verification_state": "CONFIRMED",
                    "sources": [
                        {"source_file": "a.hwp", "source_location": "p.1"},
                        {"source_file": "b.hwp", "source_location": "표1"},
                    ],
                }
            ],
            "narrative_evidence": [
                {
                    "evidence_id": "e1",
                    "text": "문제 인식 문장",
                    "category": "problem",
                    "verification_state": "CONFIRMED",
                    "source_file": "a.hwp",
                    "source_location": "p.2",
                }
            ],
            "conflicts": [],
        }
    )
    assert parsed.facts[0].sources[0].source_file == "a.hwp"
    assert parsed.facts[0].sources[1].source_location == "표1"
    payload = parsed.as_matcher_payload()
    assert payload["facts"][0]["sources"][1]["source_file"] == "b.hwp"
    assert payload["evidence"][0]["evidence_id"] == "e1"
    assert payload["facts"][0]["canonical_field"] == "대표자"


def test_parse_rejects_missing_fact_id() -> None:
    with pytest.raises(Step2ContractError, match="fact_id"):
        parse_step2_output({"facts": [{"label": "x", "value": "y"}]})


def test_parse_rejects_duplicate_ids() -> None:
    with pytest.raises(Step2ContractError, match="중복"):
        parse_step2_output(
            {
                "facts": [
                    {"fact_id": "f1", "label": "a", "value": "1"},
                    {"fact_id": "f1", "label": "b", "value": "2"},
                ]
            }
        )


def test_parse_rejects_illegal_semantic_state() -> None:
    with pytest.raises(Step2ContractError, match="semantic_state"):
        parse_step2_output(
            {"facts": [{"fact_id": "f1", "label": "a", "value": "1", "semantic_state": "GUESS"}]}
        )


def test_parse_rejects_conflict_unknown_fact() -> None:
    with pytest.raises(Step2ContractError, match="없는 fact_id"):
        parse_step2_output(
            {
                "facts": [{"fact_id": "f1", "label": "a", "value": "1"}],
                "conflicts": [{"conflict_id": "c1", "fact_ids": ["f1", "f-missing"]}],
            }
        )


def test_missing_state_defaults_to_unknown_and_is_not_invented_as_actual() -> None:
    parsed = parse_step2_output({"facts": [{"fact_id": "f1", "label": "매출", "value": "1"}]})
    assert parsed.facts[0].semantic_state == "UNKNOWN"
    assert parsed.facts[0].verification_state == "UNKNOWN"


def test_parse_does_not_create_placeholder_facts() -> None:
    parsed = parse_step2_output({"facts": [], "narrative_evidence": [], "conflicts": []})
    assert parsed.facts == []
    assert parsed.narrative_evidence == []
    assert parsed.conflicts == []
