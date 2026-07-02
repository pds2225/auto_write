"""test_pure_conversion_fidelity_helpers.py — 변환 일치도 순수 헬퍼 안전망.

conversion_fidelity 의 결정론 헬퍼(_norm_text / _ratio / _note_loss)를 외부 의존
(python-docx·한글 COM) 없이 직접 단위검증한다. 야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

from auto_write.services.conversion_fidelity import _norm_text, _note_loss, _ratio


class TestNormText:
    def test_collapses_internal_whitespace(self):
        assert _norm_text("hello  \n  world") == "hello world"

    def test_strips_ends(self):
        assert _norm_text("  x  ") == "x"

    def test_all_whitespace_becomes_empty(self):
        assert _norm_text("   \t\n ") == ""

    def test_none_is_empty(self):
        assert _norm_text(None) == ""

    def test_empty_string(self):
        assert _norm_text("") == ""

    def test_tabs_and_newlines_mixed(self):
        assert _norm_text("a\tb\nc  d") == "a b c d"


class TestRatio:
    def test_both_zero_is_full_match(self):
        # '둘 다 없음'은 완전 일치로 본다.
        assert _ratio(0, 0) == 100.0

    def test_half(self):
        assert _ratio(50, 100) == 50.0

    def test_symmetric(self):
        # min/max 기반이라 인자 순서에 무관.
        assert _ratio(100, 50) == 50.0
        assert _ratio(100, 50) == _ratio(50, 100)

    def test_equal_is_full(self):
        assert _ratio(7, 7) == 100.0

    def test_one_zero_is_zero(self):
        assert _ratio(0, 5) == 0.0
        assert _ratio(5, 0) == 0.0

    def test_rounds_to_two_decimals(self):
        assert _ratio(1, 3) == 33.33

    def test_three_quarters(self):
        assert _ratio(3, 4) == 75.0


class TestNoteLoss:
    def test_decrease_is_loss(self):
        lost: list[str] = []
        _note_loss(lost, "단락", 5, 3)
        assert lost == ["단락 수 불일치: 5 → 3 (손실 2)"]

    def test_increase(self):
        lost: list[str] = []
        _note_loss(lost, "표", 2, 5)
        assert lost == ["표 수 불일치: 2 → 5 (증가 3)"]

    def test_equal_appends_nothing(self):
        lost: list[str] = []
        _note_loss(lost, "표 셀", 4, 4)
        assert lost == []

    def test_preserves_existing_entries(self):
        lost = ["기존 항목"]
        _note_loss(lost, "이미지", 1, 0)
        assert lost == ["기존 항목", "이미지 수 불일치: 1 → 0 (손실 1)"]
