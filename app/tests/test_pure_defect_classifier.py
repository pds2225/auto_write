"""test_pure_defect_classifier.py — 자가학습 6분류(classify_check) 순수 로직 안전망.

defect_classifier 는 수용검사 결함 1건을 auto_fix/human_input/manual_review 로
분류하고, 재발(repeat_count) 시 code_improvement 로 승격한다. 외부 의존이 없어
(acceptance_remediation 의 순수 매핑표만 사용) 그대로 단위 검증한다.

여기서 고정하는 계약(야간 안전망, 2026-07-16):
- kind(auto/human/manual) → category 기본 매핑.
- §9 F1 하드 규칙: human_input 은 재발 횟수와 무관하게 **절대 승격되지 않는다**
  (승격되면 '코드가 값을 지어내야 한다'는 날조 압박이 됨).
- 승격 조건: repeat_count >= REPEAT_PROMOTE_N 이고 (manual) 또는 (auto+warn).
  auto+fail 은 이미 자동 명령으로 해결되므로 승격하지 않는다.
- command 의 {doc} 자리표시는 doc_name 을 줄 때만 치환한다(하위 호환).
"""

from __future__ import annotations

from auto_write.services.acceptance_remediation import DOC_TOKEN, KIND_AUTO, Remedy
from auto_write.services.defect_classifier import (
    CAT_AUTO_FIX,
    CAT_CODE_IMPROVEMENT,
    CAT_HUMAN_INPUT,
    CAT_MANUAL_REVIEW,
    REPEAT_PROMOTE_N,
    classify_check,
)
from auto_write.services.usage_acceptance import SEV_FAIL, SEV_WARN


def _check(check_id: str, severity: str = SEV_FAIL, **extra) -> dict:
    base = {
        "check_id": check_id,
        "label": "라벨",
        "severity": severity,
        "defects": 1,
        "samples": ["s1"],
    }
    base.update(extra)
    return base


# --- kind → category 기본 매핑 --------------------------------------------------

def test_auto_kind_maps_to_auto_fix_with_command():
    out = classify_check(_check("self_inserted_blocks"))
    assert out["category"] == CAT_AUTO_FIX
    assert "strip_notebooklm" in out["command"]     # 실행 가능한 자동 명령 제공
    assert out["next_action"]


def test_human_kind_maps_to_human_input_without_command():
    out = classify_check(_check("unresolved_markers"))
    assert out["category"] == CAT_HUMAN_INPUT
    assert out["command"] == ""                     # 사람 입력 — 자동 명령 없음


def test_manual_kind_maps_to_manual_review():
    out = classify_check(_check("masking_violation"))
    assert out["category"] == CAT_MANUAL_REVIEW


def test_unknown_check_id_falls_back_to_manual_review():
    # remedy_for 의 안전 기본값(_DEFAULT=manual)을 따른다 — 미지의 검사도 분류 실패 없음.
    out = classify_check(_check("존재하지_않는_검사"))
    assert out["category"] == CAT_MANUAL_REVIEW


# --- 재발 승격 규칙 --------------------------------------------------------------

def test_manual_promotes_to_code_improvement_at_threshold():
    out = classify_check(_check("empty_table_rows", SEV_WARN), repeat_count=REPEAT_PROMOTE_N)
    assert out["category"] == CAT_CODE_IMPROVEMENT


def test_manual_below_threshold_stays_manual_review():
    out = classify_check(_check("empty_table_rows", SEV_WARN), repeat_count=REPEAT_PROMOTE_N - 1)
    assert out["category"] == CAT_MANUAL_REVIEW


def test_auto_warn_promotes_at_threshold():
    out = classify_check(_check("font_size_spread", SEV_WARN), repeat_count=REPEAT_PROMOTE_N)
    assert out["category"] == CAT_CODE_IMPROVEMENT


def test_auto_fail_never_promotes():
    # auto+fail 은 이미 명령 한 줄로 해결 — 반복돼도 auto_fix 유지.
    out = classify_check(_check("self_inserted_blocks", SEV_FAIL), repeat_count=99)
    assert out["category"] == CAT_AUTO_FIX


def test_human_never_promotes_even_when_repeated():
    # §9 F1 하드 규칙(날조0): human_input 은 어떤 재발 횟수에도 승격 금지.
    out = classify_check(_check("unresolved_markers", SEV_FAIL), repeat_count=99)
    assert out["category"] == CAT_HUMAN_INPUT
    out2 = classify_check(_check("unchecked_choices", SEV_FAIL), repeat_count=99)
    assert out2["category"] == CAT_HUMAN_INPUT


# --- {doc} 치환·remedy 재사용·입력 정규화 ---------------------------------------

def test_doc_token_substituted_when_doc_name_given():
    out = classify_check(_check("self_inserted_blocks"), doc_name="제출본.docx")
    assert "제출본.docx" in out["command"]
    assert DOC_TOKEN not in out["command"]


def test_doc_token_kept_when_doc_name_empty():
    out = classify_check(_check("self_inserted_blocks"))
    assert DOC_TOKEN in out["command"]              # 하위 호환 — 템플릿 그대로


def test_precomputed_remedy_is_reused():
    # 호출자가 이미 계산한 Remedy 를 넘기면 remedy_for 재조회 없이 그대로 쓴다(§9 M6).
    rem = Remedy(KIND_AUTO, "커스텀 안내", f'custom.py "{DOC_TOKEN}"')
    out = classify_check(_check("존재하지_않는_검사"), remedy=rem, doc_name="a.docx")
    assert out["category"] == CAT_AUTO_FIX
    assert out["next_action"] == "커스텀 안내"
    assert out["command"] == 'custom.py "a.docx"'


def test_object_with_as_dict_is_normalized():
    class FakeCheck:
        def as_dict(self):
            return _check("masking_violation", defects=3)

    out = classify_check(FakeCheck())
    assert out["check_id"] == "masking_violation"
    assert out["defects"] == 3


def test_samples_truncated_to_five_and_none_safe():
    out = classify_check(_check("unresolved_markers", samples=[f"s{i}" for i in range(9)]))
    assert out["samples"] == ["s0", "s1", "s2", "s3", "s4"]
    out2 = classify_check(_check("unresolved_markers", samples=None))
    assert out2["samples"] == []
