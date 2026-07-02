"""test_pure_doc_quality_ops_dominant.py — 지배값 산정 순수 함수 안전망.

_dominant 은 단락 서식 통일에서 '가장 빈도 높은 실제 값'(동률은 첫 등장 우선)을 고른다.
None(명시값 없음=테마 상속)은 후보에서 제외한다. 외부 의존 없음(list → 값).
야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

from auto_write.services.doc_quality_ops import _dominant


def test_empty_list_is_none():
    assert _dominant([]) is None


def test_all_none_is_none():
    assert _dominant([None, None]) is None


def test_single_value():
    assert _dominant(["12pt"]) == "12pt"


def test_most_frequent_wins():
    assert _dominant(["a", "b", "a"]) == "a"


def test_tie_keeps_first_seen():
    # a:2, b:2 동률 → 첫 등장(a) 유지(strictly greater 비교).
    assert _dominant(["a", "b", "b", "a"]) == "a"


def test_later_value_can_win_when_strictly_more_frequent():
    assert _dominant(["b", "a", "a"]) == "a"


def test_none_excluded_from_count():
    assert _dominant([None, "x", None, "x", "y"]) == "x"


def test_realistic_font_sizes():
    assert _dominant(["10pt", "12pt", "12pt", None]) == "12pt"
