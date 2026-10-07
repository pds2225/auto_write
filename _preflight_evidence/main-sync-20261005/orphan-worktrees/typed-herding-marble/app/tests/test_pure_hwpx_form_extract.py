"""test_pure_hwpx_form_extract.py — '공고+서식' 중 서식 시작점 찾기 안전망 (순수 함수).

기관이 배포하는 HWPX 는 앞쪽에 모집공고(모집요강·수당·자격요건)가 붙어 있고 뒤쪽에
실제 제출 서식이 있다. 서식만 남기려면 **어디부터가 서식인지**를 정확히 찾아야 한다
(L037). 잘못 찾으면 공고가 제출본에 남거나(창피) 서식 앞부분이 잘린다(제출 불가).

여기서 검증하는 ``find_form_start_index``·``looks_like_notice_blob``·
``_detect_standalone`` 은 lxml 트리와 문자열만 받는 순수 함수라 파일·ZIP·한글 없이
그대로 돌린다. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- ``[서식 1]`` 표기가 있으면 **무조건 그것이 최우선**(뒤쪽에 있어도).
- 제목처럼 보이는 '참여 신청서'·'입주신청서'는 폴백이며, 제출서류 안내 목록
  ('… 1부', '- ' 로 시작, '모집공고')은 서식 시작으로 오인하지 않는다.
- 아무 마커도 없으면 ``-1`` — 호출측이 '자르지 않고 복사'로 안전하게 처리한다.
"""

from __future__ import annotations

from lxml import etree

from auto_write.services.hwpx_form_extract import (
    FormExtractReport,
    _detect_standalone,
    find_form_start_index,
    looks_like_notice_blob,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _sec(*child_texts: str):
    """직계 자식 문단 목록만 가진 섹션 루트(마커 탐색은 직계 자식 단위)."""
    body = "".join(f"<p><run><t>{t}</t></run></p>" for t in child_texts)
    return etree.fromstring(f'<sec xmlns="{_HP}">{body}</sec>'.encode("utf-8"))


# --- 1순위: 명시 [서식 1] ----------------------------------------------------

def test_explicit_form_marker_is_found():
    root = _sec("모집공고", "지원자격", "[서식 1] 참여 신청서")
    assert find_form_start_index(root) == (2, "[서식 1]")


def test_marker_without_space_is_also_found():
    root = _sec("모집공고", "[서식1]")
    assert find_form_start_index(root) == (1, "[서식 1]")


def test_explicit_marker_wins_over_title_fallback():
    # 앞쪽에 제목형 '참여 신청서'가 있어도 명시 마커를 우선한다.
    root = _sec("참여 신청서 성명", "[서식 1]")
    assert find_form_start_index(root) == (1, "[서식 1]")


# --- 2순위: '서식 1.' 목록 헤더 ----------------------------------------------

def test_numbered_form_header_is_found():
    root = _sec("붙임 서류", "서식 1. 참여 신청서")
    assert find_form_start_index(root) == (1, "서식 1.")


def test_numbered_form_header_must_be_at_line_start():
    # 문장 중간의 '서식 1.' 언급은 시작점이 아니다.
    root = _sec("자세한 내용은 서식 1. 을 참고")
    assert find_form_start_index(root) == (-1, "")


# --- 3순위: 제목형 '참여 신청서' ---------------------------------------------

def test_title_like_application_form_is_found():
    root = _sec("모집 안내", "참여 신청서\n성명 생년월일")
    idx, marker = find_form_start_index(root)
    assert (idx, marker) == (1, "참여 신청서")


def test_submission_checklist_line_is_not_a_form_start():
    # '- 참여 신청서 1부' 같은 제출서류 목록은 서식 시작이 아니다.
    root = _sec("- 참여 신청서 1부")
    assert find_form_start_index(root) == (-1, "")


def test_notice_mentioning_application_form_is_skipped():
    root = _sec("2026년 모집공고 참여 신청서 안내")
    assert find_form_start_index(root) == (-1, "")


def test_bare_title_ending_with_application_form_is_accepted():
    root = _sec("공고문", "전문상담위원 참여 신청서")
    assert find_form_start_index(root) == (1, "참여 신청서")


# --- 4·5순위: 붙임/입주신청서 ------------------------------------------------

def test_attachment_header_with_business_plan_is_found():
    root = _sec("공고", "붙 임 1  입주신청서 및 사업계획서")
    assert find_form_start_index(root) == (1, "붙 임1")


def test_move_in_form_title_is_found():
    root = _sec("공고문", "창업지원센터 입주신청서")
    assert find_form_start_index(root) == (1, "입주신청서")


def test_required_documents_line_is_not_move_in_form_start():
    root = _sec("제출 서류: 입주신청서 1부")
    assert find_form_start_index(root) == (-1, "")


# --- 마커 없음 ---------------------------------------------------------------

def test_no_marker_returns_minus_one():
    root = _sec("모집공고", "지원자격", "문의처")
    assert find_form_start_index(root) == (-1, "")


def test_empty_section_returns_minus_one():
    assert find_form_start_index(_sec()) == (-1, "")


# --- looks_like_notice_blob --------------------------------------------------

def test_notice_blob_needs_two_signals():
    assert looks_like_notice_blob("모집공고 수당지급 기준") is True
    assert looks_like_notice_blob("모집공고만 있음") is False
    assert looks_like_notice_blob("") is False


def test_notice_blob_detects_other_keyword_pairs():
    assert looks_like_notice_blob("위촉기간 및 접수기간 안내") is True
    assert looks_like_notice_blob("모집인원 20명, 접수기간 2주") is True


def test_clean_form_text_is_not_a_notice():
    assert looks_like_notice_blob("성명 생년월일 연락처 참여 신청서") is False


# --- _detect_standalone (XML 선언 보존) --------------------------------------

def test_detect_standalone_yes_no_and_absent():
    assert _detect_standalone(b'<?xml version="1.0" standalone="yes"?><sec/>') is True
    assert _detect_standalone(b"<?xml version='1.0' standalone='no'?><sec/>") is False
    assert _detect_standalone(b'<?xml version="1.0"?><sec/>') is None


def test_detect_standalone_only_reads_the_declaration_head():
    # 본문 한참 뒤의 standalone 문자열에 속지 않는다(선언부 200바이트만 확인).
    blob = b'<?xml version="1.0"?><sec>' + b"x" * 300 + b'standalone="yes"</sec>'
    assert _detect_standalone(blob) is None


# --- FormExtractReport -------------------------------------------------------

def test_report_defaults_are_not_ok():
    rep = FormExtractReport(input="a.hwpx")
    assert rep.ok is False and rep.start_index == -1 and rep.marker == ""


def test_report_as_dict_round_trip():
    rep = FormExtractReport(
        input="a.hwpx", output="b.hwpx", ok=True, start_index=3,
        marker="[서식 1]", kids_before=10, kids_after=7, notes=["잘림"],
    )
    data = rep.as_dict()
    assert data["ok"] is True and data["marker"] == "[서식 1]"
    assert data["kids_before"] - data["kids_after"] == 3
    assert data["notes"] == ["잘림"]
