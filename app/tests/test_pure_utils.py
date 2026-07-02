"""test_pure_utils.py — 공통 유틸 순수 함수 안전망.

utils 의 외부 의존 없는 순수 함수를 직접 검증한다(기존 테스트 전무 영역):
- slugify: 유니코드→ascii 슬러그(빈 결과는 prefix+uuid 폴백)
- sanitize_user_filename: 사용자 파일명 정화 — 경로 탈출/예약어/제어문자 차단 [보안]
- safe_console_text: 콘솔 출력용 특수문자 치환
- unique_lines: 공백/중복 줄 제거(순서 유지)

야간 순수함수 안전망(2026-07-02).
"""

from __future__ import annotations

import pytest

from auto_write.utils import (
    safe_console_text,
    sanitize_user_filename,
    slugify,
    unique_lines,
)


class TestSlugify:
    def test_ascii_words(self):
        assert slugify("Hello World") == "hello_world"

    def test_strips_and_lowercases(self):
        assert slugify("  API-Key Report  ") == "api_key_report"

    def test_unicode_stripped_to_ascii(self):
        # NFKD 분해 후 ascii 로만 — 결합문자/이모지는 제거된다.
        assert slugify("café ☕") == "cafe"

    def test_non_ascii_only_falls_back_to_prefix(self):
        out = slugify("한글만", prefix="doc")
        assert out.startswith("doc_")
        assert len(out) > len("doc_")

    def test_empty_uses_default_prefix(self):
        assert slugify("").startswith("item_")

    def test_length_capped_at_48(self):
        assert len(slugify("a" * 100)) == 48


class TestSafeConsoleText:
    def test_em_and_en_dash(self):
        assert safe_console_text("a—b–c") == "a-b-c"

    def test_bullets(self):
        assert safe_console_text("• ●") == "* *"

    def test_check_marks(self):
        assert safe_console_text("✓✅") == "[OK][OK]"

    def test_warning(self):
        assert safe_console_text("⚠ 주의") == "[WARN] 주의"

    def test_camera_and_double_line(self):
        assert safe_console_text("\U0001F4F8═") == "[IMG]="

    def test_plain_text_unchanged(self):
        assert safe_console_text("보통 텍스트 abc 123") == "보통 텍스트 abc 123"


class TestUniqueLines:
    def test_dedup_and_strip(self):
        assert unique_lines("a\nb\na\n\n  c  ") == ["a", "b", "c"]

    def test_empty(self):
        assert unique_lines("") == []

    def test_all_blank(self):
        assert unique_lines("  \n\t\n   ") == []

    def test_repeated_single(self):
        assert unique_lines("x\nx\nx") == ["x"]


class TestSanitizeUserFilename:
    def test_normal_name(self):
        assert sanitize_user_filename("report.docx") == "report.docx"

    def test_collapses_inner_whitespace(self):
        assert sanitize_user_filename("my   file.docx") == "my file.docx"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            sanitize_user_filename("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            sanitize_user_filename("   ")

    def test_forward_slash_raises(self):
        with pytest.raises(ValueError):
            sanitize_user_filename("dir/file.txt")

    def test_backslash_raises(self):
        with pytest.raises(ValueError):
            sanitize_user_filename("dir\\file.txt")

    def test_parent_dir_raises(self):
        with pytest.raises(ValueError):
            sanitize_user_filename("..evil.txt")

    def test_reserved_name_raises(self):
        with pytest.raises(ValueError):
            sanitize_user_filename("CON.txt")

    def test_control_and_forbidden_chars_replaced(self):
        # 경로 구분자는 위에서 이미 차단, 나머지 금지문자는 '_' 로 치환.
        assert sanitize_user_filename("a<b>c.txt") == "a_b_c.txt"

    def test_long_name_trimmed(self):
        out = sanitize_user_filename("x" * 300 + ".txt")
        assert len(out) <= 180
        assert out.endswith(".txt")
