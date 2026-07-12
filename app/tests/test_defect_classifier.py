"""defect_classifier 자가학습 6분류 테스트.

AUTO→auto_fix / HUMAN→human_input / §9 F1(human 재발 → code_improvement 승격 금지) /
manual repeat>=3→code_improvement / 미등록 check_id→manual_review(_DEFAULT).
"""

from __future__ import annotations

from auto_write.services.defect_classifier import (
    CAT_AUTO_FIX,
    CAT_CODE_IMPROVEMENT,
    CAT_HUMAN_INPUT,
    CAT_MANUAL_REVIEW,
    REPEAT_PROMOTE_N,
    classify_check,
)
from auto_write.services.usage_acceptance import SEV_FAIL, CheckResult


def _check_dict(check_id: str, severity: str = SEV_FAIL, defects: int = 1) -> dict:
    return {
        "check_id": check_id,
        "label": check_id,
        "severity": severity,
        "defects": defects,
        "samples": ["샘플1"],
        "detail": "",
    }


def test_auto_kind_classified_as_auto_fix() -> None:
    # self_inserted_blocks 는 acceptance_remediation 에서 KIND_AUTO.
    result = classify_check(_check_dict("self_inserted_blocks"))
    assert result["category"] == CAT_AUTO_FIX
    assert result["command"]  # 자동 명령이 있어야 한다


def test_human_kind_classified_as_human_input() -> None:
    # unresolved_markers 는 KIND_HUMAN.
    result = classify_check(_check_dict("unresolved_markers"))
    assert result["category"] == CAT_HUMAN_INPUT


def test_recurring_human_check_never_promoted_to_code_improvement() -> None:
    """§9 F1 하드 규칙 — human_input 은 repeat_count 가 아무리 커도 승격 금지(날조0 최우선)."""
    result = classify_check(_check_dict("unresolved_markers"), repeat_count=99)
    assert result["category"] == CAT_HUMAN_INPUT
    assert result["category"] != CAT_CODE_IMPROVEMENT


def test_manual_kind_repeat_promotes_to_code_improvement() -> None:
    # masking_violation 은 KIND_MANUAL. repeat_count>=REPEAT_PROMOTE_N 이면 승격된다.
    below = classify_check(_check_dict("masking_violation"), repeat_count=REPEAT_PROMOTE_N - 1)
    at = classify_check(_check_dict("masking_violation"), repeat_count=REPEAT_PROMOTE_N)
    assert below["category"] == CAT_MANUAL_REVIEW
    assert at["category"] == CAT_CODE_IMPROVEMENT


def test_unregistered_check_id_falls_back_to_manual_review() -> None:
    result = classify_check(_check_dict("존재하지_않는_검사"))
    assert result["category"] == CAT_MANUAL_REVIEW


def test_auto_command_substitutes_doc_token_when_doc_name_given() -> None:
    """command 의 {doc} 자리표시가 실제 문서 경로로 치환돼야 복붙 실행 가능하다."""
    result = classify_check(_check_dict("self_inserted_blocks"), doc_name="results/제출본.docx")
    assert "{doc}" not in result["command"]
    assert "results/제출본.docx" in result["command"]


def test_auto_command_keeps_placeholder_when_doc_name_omitted() -> None:
    result = classify_check(_check_dict("self_inserted_blocks"))
    assert "{doc}" in result["command"]


def test_classify_check_accepts_real_checkresult_object() -> None:
    cr = CheckResult(
        check_id="self_inserted_blocks", label="라벨", severity=SEV_FAIL,
        defects=2, samples=["a", "b"], detail="상세",
    )
    result = classify_check(cr)
    assert result["category"] == CAT_AUTO_FIX
    assert result["defects"] == 2
    assert result["samples"] == ["a", "b"]
