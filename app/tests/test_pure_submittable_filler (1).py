# -*- coding: utf-8 -*-
"""submittable_filler.SubmittableFiller 의 순수 라벨 정규화 헬퍼 회귀 안전망.

표 채우기에서 라벨을 비교할 때 쓰는 두 staticmethod 는 외부 의존이 없다:
- _norm: 연속 공백을 1칸으로 줄이고 양끝 공백 제거(None→'').
- _key: 괄호 보조설명 '(...)' 을 통째로 제거하고 모든 공백을 없앤 '핵심 키'.
  '기업 명 (주식회사)' 와 '기업명' 이 같은 칸으로 인식되려면 이 정규화가 일정해야 한다.

기대값은 실제 함수를 실행해 고정했다.
"""
from auto_write.services.submittable_filler import SubmittableFiller as SF


# ------------------------------------------------------------------------ _norm
def test_norm_collapses_inner_whitespace():
    assert SF._norm("  a  b  ") == "a b"


def test_norm_treats_newline_tab_as_whitespace():
    assert SF._norm("a\n\tb") == "a b"


def test_norm_empty_and_none():
    assert SF._norm("") == ""
    assert SF._norm(None) == ""


def test_norm_single_token_trims():
    assert SF._norm(" 단일 ") == "단일"


# ------------------------------------------------------------------------- _key
def test_key_removes_parenthetical_and_spaces():
    assert SF._key("기업 명 (주식회사)") == "기업명"


def test_key_removes_all_whitespace():
    assert SF._key("대표자 성명") == "대표자성명"


def test_key_strips_trailing_parenthetical():
    assert SF._key("전화 (휴대)") == "전화"
    assert SF._key("연락처(휴대폰/유선)") == "연락처"


def test_key_all_parenthetical_becomes_empty():
    assert SF._key("(전부괄호)") == ""


def test_key_empty():
    assert SF._key("") == ""
