"""cross_form_autofill 순수 판별 헬퍼 단위 안전망.

전사 엔진의 '안전 핵심' 결정 함수들(이름 모양 가드·괄호 구별·빈칸 판정·선택칸
파싱·자카드 유사도·라벨 장식 제거·요약 표시)을 문서/파일 I/O 없이 직접 단위
검증한다. 이 함수들은 "오매칭은 빈칸보다 나쁘다"·"실값 덮어쓰기 금지"·"날조 0"
불변을 코드로 강제하는 지점이라, 회귀가 나면 실제 양식에서 값이 잘못 채워진다.

읽기 전용·결정론 — Document/COM/네트워크를 전혀 건드리지 않는다.
"""

from __future__ import annotations

from auto_write.services.cross_form_autofill import (
    _bracket_conflict,
    _bracket_tokens,
    _cluster_rep,
    _confirm_hint,
    _is_fill_blank,
    _is_name_field,
    _is_option_cell,
    _is_visible_blank,
    _jaccard,
    _key,
    _looks_like_name,
    _looks_numeric,
    _normalize_choice,
    _option_text,
    _strip_label_decoration,
    _summary_shorten,
    _tokens,
)


# --- 이름(성명) 모양 가드: 역할서술이 이름칸에 자동전사되는 실측 오류 차단 ---------

def test_looks_like_name_accepts_short_plain_names() -> None:
    assert _looks_like_name("홍길동") is True
    assert _looks_like_name("김철수") is True
    assert _looks_like_name("John Smith") is True
    assert _looks_like_name("○○○") is True          # 블라인드 마스킹 이름은 허용


def test_looks_like_name_rejects_role_descriptions_and_lists() -> None:
    # 역할분담 서술(콤마·및·총괄)은 이름이 아니다 → high 전사 차단
    assert _looks_like_name("기술개발, 특허전략 및 사업화 총괄") is False
    assert _looks_like_name("홍길동 및 김철수") is False
    assert _looks_like_name("개발 담당") is False
    assert _looks_like_name("A·B·C") is False


def test_looks_like_name_rejects_empty_and_overlong() -> None:
    assert _looks_like_name("") is False
    assert _looks_like_name("   ") is False
    assert _looks_like_name("가" * 20) is True       # 경계: 20자까지는 이름 허용
    assert _looks_like_name("가" * 21) is False      # 21자↑는 서술로 간주


# --- 동의어 클러스터 조회 / 이름필드 판정 -------------------------------------

def test_cluster_rep_known_and_unknown() -> None:
    assert _cluster_rep(_key("대표자")) is not None
    # 같은 클러스터의 별칭은 동일 대표키를 가리킨다
    assert _cluster_rep(_key("대표자명")) == _cluster_rep(_key("성명"))
    assert _cluster_rep("완전히잡음xyz없는라벨") is None


def test_is_name_field_membership() -> None:
    assert _is_name_field(_key("대표자")) is True
    assert _is_name_field(_key("성명")) is True
    assert _is_name_field(_key("대표자명")) is True
    # 담당자명은 대표자 클러스터와 분리(실무담당자) — 이름필드 아님
    assert _is_name_field(_key("담당자명")) is False
    assert _is_name_field(_key("주소")) is False
    assert _is_name_field("미등록라벨qwer") is False


# --- 괄호 토큰 구별: '금액(국고)' vs '금액(자부담)' 같은 항목을 high 매칭 금지 ----

def test_bracket_tokens_extracts_inner() -> None:
    assert _bracket_tokens("금액(국고)") == {"국고"}
    assert _bracket_tokens("총액（자부담）") == {"자부담"}   # 전각 괄호도 인식
    assert _bracket_tokens("사업비(국고)(자부담)") == {"국고", "자부담"}
    assert _bracket_tokens("금액") == set()               # 괄호 없음
    assert _bracket_tokens("금액(  )") == set()           # 공백만 → 토큰 없음


def test_bracket_conflict_detects_distinct_qualifiers() -> None:
    assert _bracket_conflict("금액(국고)", "금액(자부담)") is True
    # 같은 괄호 토큰이면 충돌 아님
    assert _bracket_conflict("금액(국고)", "지원금(국고)") is False
    # 한쪽에 괄호가 없으면 충돌 판단 불가 → False(보수)
    assert _bracket_conflict("금액", "금액(국고)") is False
    assert _bracket_conflict("금액(국고)", "금액") is False


# --- 순수 숫자/금액/날짜 값 판정(라벨로 둔갑 차단용) ---------------------------

def test_looks_numeric_true_for_number_like_values() -> None:
    assert _looks_numeric("30,000,000") is True
    assert _looks_numeric("60,000원") is True
    assert _looks_numeric("2026-04-10") is True
    assert _looks_numeric("2026.04.10") is True
    assert _looks_numeric("10%") is True
    assert _looks_numeric("3개") is True


def test_looks_numeric_false_for_text_and_empty() -> None:
    assert _looks_numeric("매출액") is False
    assert _looks_numeric("홍길동") is False
    assert _looks_numeric("") is False
    assert _looks_numeric("   ") is False
    assert _looks_numeric("대표자명") is False


# --- 빈칸 판정: _is_fill_blank(콜론 뒤 완전 빈칸 허용) vs _is_visible_blank ------

def test_is_fill_blank_recognizes_blank_markers_only() -> None:
    assert _is_fill_blank("") is True
    assert _is_fill_blank("     ") is True
    assert _is_fill_blank("______") is True
    assert _is_fill_blank("......") is True
    assert _is_fill_blank("─────") is True
    # 실제 글자/마스킹/체크박스가 있으면 빈칸 아님(덮어쓰기 금지)
    assert _is_fill_blank("홍길동") is False
    assert _is_fill_blank("○○○") is False
    assert _is_fill_blank("___값") is False


def test_is_visible_blank_requires_actual_fill_line() -> None:
    # 표 셀 인라인 전용: 콜론 뒤가 '완전히 비면' 옆 값칸과 구별 불가 → 인정 안 함
    assert _is_visible_blank("") is False
    assert _is_visible_blank("     ") is False
    # 밑줄·점 등 '보이는 채움선'이 있어야 인정
    assert _is_visible_blank("______") is True
    assert _is_visible_blank(".....") is True
    assert _is_visible_blank("○○○") is False
    assert _is_visible_blank("값") is False


# --- 선택칸(체크박스) 파싱: 정확일치만 인정(부분문자열 오체크 방지) -------------

def test_normalize_choice_maps_known_synonyms_else_identity() -> None:
    assert _normalize_choice("개인사업자") == "개인"
    assert _normalize_choice("개인기업") == "개인"
    assert _normalize_choice("주식회사") == "법인"
    assert _normalize_choice("법인") == "법인"
    # 사전에 없는 값은 그대로 둔다(서술형·절단값은 자동으로 보류됨)
    assert _normalize_choice("서술형기타값") == "서술형기타값"


def test_option_text_strips_box_symbol() -> None:
    assert _option_text("□ 개인") == "개인"
    assert _option_text("■법인") == "법인"
    assert _option_text("  ☑ 해당  ") == "해당"
    assert _option_text("개인") == "개인"            # 박스 없으면 그대로


def test_is_option_cell_requires_exactly_one_box_and_a_word() -> None:
    assert _is_option_cell("□ 개인") is True
    assert _is_option_cell("■ 법인") is True
    assert _is_option_cell("개인") is False          # 박스 0개 = 일반 라벨/값
    assert _is_option_cell("□ 개인 □ 법인") is False  # 박스 2개 = 위치 모호
    assert _is_option_cell("□") is False             # 옵션명 없는 단독 박스(매트릭스 체크칸)


# --- 문자 자카드 유사도(퍼지 매칭 기반) ----------------------------------------

def test_tokens_is_character_set() -> None:
    assert _tokens("기업명") == {"기", "업", "명"}
    assert _tokens("") == set()


def test_jaccard_similarity() -> None:
    assert _jaccard(set(), {"a"}) == 0.0
    assert _jaccard({"a", "b"}, set()) == 0.0
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert _jaccard({"a", "b", "c"}, {"a", "b"}) == 2 / 3
    assert _jaccard({"a"}, {"b"}) == 0.0


# --- 라벨 장식(글머리표/순번) 제거 — 의미는 보존 ------------------------------

def test_strip_label_decoration_removes_bullets_and_numbers() -> None:
    assert _strip_label_decoration("○기업명") == "기업명"
    assert _strip_label_decoration("1.사업명") == "사업명"
    assert _strip_label_decoration("▶ 대표자") == "대표자"


def test_strip_label_decoration_preserves_meaningful_prefixes() -> None:
    # 구분자(./)) 없는 정상 라벨은 깎지 않는다
    assert _strip_label_decoration("1차년도") == "1차년도"
    # 전부-기호(마스킹 라벨)는 원본 보존(글자가 하나도 안 남으면 되돌림)
    assert _strip_label_decoration("○○○") == "○○○"


def test_key_ignores_decoration_for_equality() -> None:
    # 장식만 다른 라벨은 같은 비교 키를 가진다(recall↑, 오매칭은 새로 안 생김)
    assert _key("○기업명") == _key("기업명")
    assert _key("1. 사업명") == _key("사업명")


# --- 요약 표시 헬퍼(값 변경 없음, 표시 전용) ----------------------------------

def test_summary_shorten_collapses_ws_and_truncates() -> None:
    assert _summary_shorten("a b  c\nd") == "a b c d"     # 공백 정규화
    assert _summary_shorten("짧은값") == "짧은값"
    long = _summary_shorten("가" * 50, limit=40)
    assert len(long) == 40 and long.endswith("…")
    assert _summary_shorten(None) == ""


def test_confirm_hint_inline_vs_file_for_special_chars() -> None:
    # 특수문자 없으면 복붙 가능한 인라인 명령
    assert _confirm_hint("대표자명", "홍길동") == '--confirm "대표자명=홍길동"'
    # 라벨/값에 " 나 = 가 있으면 파싱이 깨지므로 --confirm-file(JSON) 안내
    hint = _confirm_hint("금액=원", "값")
    assert "--confirm-file" in hint
    assert "금액=원" in hint       # JSON 안에 원본 라벨이 손상 없이 담긴다
