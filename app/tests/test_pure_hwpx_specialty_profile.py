"""test_pure_hwpx_specialty_profile.py — 모집분야 confirm→체크좌표 안전망 (순수 함수).

정부 신청서의 '모집분야' 체크박스는 **사용자가 확인해 준 분야만** 체크해야 한다
(L034·모듈 최상단 원칙 "추정 자동체크 금지"). ``resolve_specialty_checks`` 는 사용자가
말한 분야 문구를 표 좌표 ``(col, row, label)`` 로 바꾸는 순수 함수라 파일·한글 없이
검증한다. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 정확한 분야명·짧은 별칭('특화')은 그대로 확정된다.
- **모호한 말('경영'·'전문상담')은 추측하지 않고 에러**를 낸다 — 예전에는 조용히
  첫 번째 분야(경영기반)를 체크해, 사용자가 고르지 않은 칸이 제출본에 찍힐 수 있었다.
- 모르는 말은 에러, 빈 문자열은 무시, 같은 분야를 두 번 말해도 한 번만 체크한다.
"""

from __future__ import annotations

import pytest

from auto_write.services.hwpx_specialty_profile import (
    MINWON_SPECIALTY_OPTIONS,
    SpecialtyConfirmError,
    resolve_specialty_checks,
)

_기반 = (1, 4, "경영기반 전문상담")
_활동 = (2, 4, "경영활동 전문상담")
_특화 = (3, 4, "특화분야 전문상담")


# --- 정상 확정 ---------------------------------------------------------------

def test_no_confirm_checks_nothing():
    # confirm 이 없으면 아무 칸도 체크하지 않는다(추정 금지의 기본값).
    assert resolve_specialty_checks([]) == []
    assert resolve_specialty_checks(["", "   "]) == []


def test_exact_label_resolves_to_coordinates():
    assert resolve_specialty_checks(["경영기반 전문상담"]) == [_기반]
    assert resolve_specialty_checks(["경영활동 전문상담"]) == [_활동]
    assert resolve_specialty_checks(["특화분야 전문상담"]) == [_특화]


def test_alias_resolves_without_full_label():
    # 사용자가 줄여 말해도(별칭) 한 분야로만 특정되면 확정한다.
    assert resolve_specialty_checks(["경영기반"]) == [_기반]
    assert resolve_specialty_checks(["활동"]) == [_활동]
    assert resolve_specialty_checks(["특화"]) == [_특화]
    assert resolve_specialty_checks(["기반"]) == [_기반]


def test_multiple_confirms_keep_user_order():
    assert resolve_specialty_checks(["특화", "경영기반"]) == [_특화, _기반]


def test_duplicate_confirm_checks_once():
    # 같은 분야를 별칭·정식명으로 두 번 말해도 체크는 한 번(중복 좌표 방지).
    assert resolve_specialty_checks(["경영기반", "경영기반 전문상담"]) == [_기반]


def test_blank_entries_are_skipped_not_errors():
    assert resolve_specialty_checks(["", "특화", "  "]) == [_특화]


def test_unknown_profile_falls_back_to_default():
    assert resolve_specialty_checks(["특화"], profile="존재하지않는양식") == [_특화]


# --- 모호·불명 차단 (추정 자동체크 금지) --------------------------------------

def test_ambiguous_prefix_raises_instead_of_guessing():
    # '경영'은 경영기반·경영활동 둘 다에 해당 → 추측 금지, 사용자에게 되묻게 한다.
    with pytest.raises(SpecialtyConfirmError) as exc:
        resolve_specialty_checks(["경영"])
    msg = str(exc.value)
    assert "모호" in msg
    assert "경영기반 전문상담" in msg and "경영활동 전문상담" in msg


def test_ambiguous_common_suffix_raises():
    # '전문상담'은 세 분야 라벨 모두에 들어 있다 → 모호.
    with pytest.raises(SpecialtyConfirmError):
        resolve_specialty_checks(["전문상담"])


def test_ambiguous_token_checks_nothing_at_all():
    # 모호한 토큰이 뒤에 섞여 있으면 앞의 정상 항목까지 통째로 중단된다
    # (반쪽만 체크된 제출본이 나가지 않게).
    with pytest.raises(SpecialtyConfirmError):
        resolve_specialty_checks(["특화", "경영"])


def test_unknown_confirm_raises_with_allowed_list():
    with pytest.raises(SpecialtyConfirmError) as exc:
        resolve_specialty_checks(["해외마케팅"])
    msg = str(exc.value)
    assert "불명" in msg
    assert "경영기반 전문상담" in msg  # 허용 목록을 함께 안내


def test_error_is_a_valueerror_subclass():
    # 호출측(cross_form_hwp_pipeline)이 ValueError 로도 잡을 수 있어야 한다.
    assert issubclass(SpecialtyConfirmError, ValueError)


# --- 좌표 맵 자체 ------------------------------------------------------------

def test_profile_options_are_three_distinct_columns_on_same_row():
    cols = [o.col for o in MINWON_SPECIALTY_OPTIONS]
    rows = {o.row for o in MINWON_SPECIALTY_OPTIONS}
    assert cols == [1, 2, 3]
    assert rows == {4}  # 실측: row3=라벨, row4=checkBtn


def test_every_option_label_is_self_resolvable():
    # 좌표 맵에 새 분야를 추가해도 '정식 라벨로는 항상 확정된다'를 보장.
    for opt in MINWON_SPECIALTY_OPTIONS:
        assert resolve_specialty_checks([opt.label]) == [(opt.col, opt.row, opt.label)]
