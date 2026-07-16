"""test_pure_announcement_heuristic.py — announcement_analyzer 순수 휴리스틱 회귀.

AI·파일 I/O 없이 정규식 기반 핵심정보 추출만 검증한다(결정론).

핵심: 금액 추출이 '숫자+단위'(예: 1억원)를 보존하는지 회귀로 고정한다.
과거에는 단위가 캡처 그룹(())이라 ``re.findall`` 이 그룹만 반환해 숫자를 버리고
"억원"만 남는 버그가 있었다(비캡처 (?:...) 로 수정). 이 파일이 그 회귀를 막는다.
"""

from __future__ import annotations

from auto_write.services.announcement_analyzer import (
    _AMOUNT_RE,
    _ELIG_RE,
    _collect_lines,
    _heuristic_key_info,
)


def test_amount_regex_returns_full_match_not_only_unit():
    # findall 은 숫자+단위 전체를 반환해야 한다(단위만 X).
    assert _AMOUNT_RE.findall("최대 1억원 지원") == ["1억원"]
    assert _AMOUNT_RE.findall("3,000만원 규모") == ["3,000만원"]


def test_heuristic_funding_amount_preserves_digits():
    info = _heuristic_key_info("지원금액: 최대 1억원 이내")
    assert info["funding_amount"] == "1억원"


def test_heuristic_funding_amount_dedup_and_sorted():
    text = "1억원 지원, 다른 사업 5천만원, 또 1억원"
    fa = _heuristic_key_info(text)["funding_amount"]
    parts = fa.split(", ")
    # 중복 제거 + 정렬(결정론) — 같은 금액이 두 번 나와도 한 번만.
    assert parts == sorted(set(parts))
    assert parts.count("1억원") == 1
    assert "5천만원" in parts


def test_heuristic_funding_amount_empty_when_no_amount():
    info = _heuristic_key_info("금액 정보는 별도 안내 예정")
    assert info["funding_amount"] == ""


def test_heuristic_key_info_has_all_schema_keys():
    # 스키마 키가 항상 존재해야 다운스트림(folder_analyzer 요약)에서 KeyError 없음.
    info = _heuristic_key_info("지원대상: 예비창업자\n지원금액: 최대 1억원")
    for key in (
        "support_target", "eligibility", "funding_amount", "deadline",
        "required_documents", "support_content", "bonus_points", "notes",
    ):
        assert key in info


def test_collect_lines_matches_and_respects_limit():
    text = "\n".join([
        "지원대상: 예비창업자",
        "무관한 줄",
        "신청자격: 만 39세 이하",
        "지원 대상: 중소기업",
    ])
    lines = _collect_lines(text, _ELIG_RE, limit=2)
    assert len(lines) == 2                      # limit 로 조기 종료
    assert lines[0] == "지원대상: 예비창업자"


def test_collect_lines_truncates_long_line_to_120():
    long_line = "지원대상: " + "가" * 300
    lines = _collect_lines(long_line, _ELIG_RE, limit=5)
    assert len(lines) == 1
    assert len(lines[0]) == 120                 # s[:120] 잘림
