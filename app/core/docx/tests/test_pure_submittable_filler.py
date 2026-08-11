"""test_pure_submittable_filler.py — 제출 마감 후처리기 순수 헬퍼 안전망.

SubmittableFiller 의 정적 헬퍼(_norm / _key)와 잔여 더미 토큰 정규식(RESIDUAL_RE)을
외부 의존(python-docx) 없이 직접 검증한다. 야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

from auto_write.services.submittable_filler import SubmittableFiller


class TestNorm:
    def test_collapse_and_strip(self):
        assert SubmittableFiller._norm("hello \n\n  world") == "hello world"

    def test_none(self):
        assert SubmittableFiller._norm(None) == ""

    def test_empty(self):
        assert SubmittableFiller._norm("") == ""

    def test_trim(self):
        assert SubmittableFiller._norm("  x  ") == "x"


class TestKey:
    def test_removes_parenthetical(self):
        assert SubmittableFiller._key("기업명 (사업자등록번호)") == "기업명"

    def test_removes_internal_space(self):
        assert SubmittableFiller._key("기업 명") == "기업명"

    def test_multiple_parens(self):
        assert SubmittableFiller._key("A (x) B (y)") == "AB"

    def test_none_and_empty(self):
        assert SubmittableFiller._key(None) == ""
        assert SubmittableFiller._key("") == ""


class TestResidualRegex:
    def test_ooo_marker(self):
        assert SubmittableFiller.RESIDUAL_RE.search("대표자 OOO 입력") is not None

    def test_million_won_dummy(self):
        assert SubmittableFiller.RESIDUAL_RE.search("매출 00백만원") is not None

    def test_biznum_dummy(self):
        assert SubmittableFiller.RESIDUAL_RE.search("사업자 OOO-OO-OOOOO") is not None

    def test_ellipsis(self):
        assert SubmittableFiller.RESIDUAL_RE.search("내용 ...") is not None

    def test_clean_text_has_no_residual(self):
        assert SubmittableFiller.RESIDUAL_RE.search("2026년 매출 10억원 달성") is None
