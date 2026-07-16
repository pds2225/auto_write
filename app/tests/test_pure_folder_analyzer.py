"""test_pure_folder_analyzer.py — folder_analyzer 순수 헬퍼 회귀.

파일 시스템 접근 없이(경로 문자열만) 판별·포매팅 헬퍼를 고정한다.
"""

from __future__ import annotations

from pathlib import Path

from auto_write.services.folder_analyzer import (
    _ANNOUNCEMENT_NAME_KEYWORDS,
    _fmt_list,
    _name_has_keyword,
    is_announcement_file,
)


def test_fmt_list_joins_and_drops_falsy():
    assert _fmt_list(["a", "b"]) == "a, b"
    assert _fmt_list(["a", "", None, "c"]) == "a, c"   # 빈/None 제거
    assert _fmt_list([]) == ""


def test_fmt_list_scalar_and_empty():
    assert _fmt_list("hello") == "hello"
    assert _fmt_list("") == ""
    assert _fmt_list(None) == ""
    assert _fmt_list(0) == ""                           # falsy 스칼라 → 빈 문자열
    assert _fmt_list(5) == "5"


def test_name_has_keyword_case_insensitive():
    assert _name_has_keyword("모집공고", _ANNOUNCEMENT_NAME_KEYWORDS) is True
    assert _name_has_keyword("사업계획서", _ANNOUNCEMENT_NAME_KEYWORDS) is False


def test_is_announcement_file_by_name_and_extension():
    assert is_announcement_file(Path("모집공고.txt")) is True
    assert is_announcement_file(Path("2026_창업_공고문.hwp")) is True
    assert is_announcement_file(Path("행사모집.pdf")) is True
    # 이름은 맞지만 지원하지 않는 확장자 → False
    assert is_announcement_file(Path("공고.jpg")) is False
    # 확장자는 맞지만 공고 키워드 없음 → False
    assert is_announcement_file(Path("참가신청서.docx")) is False
