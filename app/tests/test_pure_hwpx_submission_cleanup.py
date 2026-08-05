"""test_pure_hwpx_submission_cleanup.py — 제출본 공통 후처리 안전망 (순수 함수).

채워진 HWPX 를 제출 직전에 다듬는 공통 규칙이다 — 예시용 색 글자를 검정으로,
'작성요령 … 삭제 후 제출' 같은 양식 안내를 제거, 본문에서 작성 메모를 지운다.
ZIP 을 만드는 ``finalize_submission_hwpx`` 를 뺀 나머지는 lxml 트리·문자열만 받는
순수 로직이라 파일 없이 그대로 검증한다. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 글자색은 **흰색(어두운 칸용)과 이미 검정인 것은 건드리지 않고**, 나머지 색만 검정으로.
- 안내문구는 핵심어(작성요령 등)와 보조어(삭제 후 제출 등)를 **동시에** 만족할 때만
  지운다 — 비슷한 말이 섞인 본문을 잘못 지우지 않는다(오삭제 금지).
- 제목 정리는 **멱등** — 이미 정리된 줄을 다시 넣어도 글자가 사라지지 않는다.
"""

from __future__ import annotations

from lxml import etree

from auto_write.services.hwpx_submission_cleanup import (
    force_black_text,
    reformat_bullet_heading,
    remove_form_guides,
    strip_meta_notes,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _root(xml: str):
    return etree.fromstring(xml.encode("utf-8"))


def _sec(body: str):
    return _root(f'<sec xmlns="{_HP}">{body}</sec>')


def _para(text: str) -> str:
    return f"<p><run><t>{text}</t></run></p>"


def _tbl(text: str) -> str:
    return f"<tbl><tr><tc>{_para(text)}</tc></tr></tbl>"


def _texts(root) -> list[str]:
    return [t.text or "" for t in root.iter(f"{{{_HP}}}t")]


# --- force_black_text -------------------------------------------------------

def test_colored_charpr_becomes_black():
    root = _root('<head><charPr textColor="#808080"/><charPr textColor="0000FF"/></head>')
    assert force_black_text(root) == 2
    assert [c.get("textColor") for c in root] == ["#000000", "#000000"]


def test_white_text_is_preserved_for_dark_cells():
    # 어두운 배경 칸의 흰 글자를 검정으로 바꾸면 글자가 안 보이게 된다.
    root = _root('<head><charPr textColor="#FFFFFF"/><charPr textColor="ffffff"/></head>')
    assert force_black_text(root) == 0
    assert [c.get("textColor") for c in root] == ["#FFFFFF", "ffffff"]


def test_already_black_is_left_alone():
    root = _root('<head><charPr textColor="000000"/></head>')
    assert force_black_text(root) == 0
    assert root[0].get("textColor") == "000000"  # 불필요한 재기록 없음


def test_charpr_without_color_is_untouched():
    root = _root("<head><charPr/><charPr textColor=''/></head>")
    assert force_black_text(root) == 0
    assert root[0].get("textColor") is None


def test_non_charpr_elements_are_ignored():
    root = _root('<head><fontface textColor="#FF0000"/></head>')
    assert force_black_text(root) == 0
    assert root[0].get("textColor") == "#FF0000"


# --- remove_form_guides -----------------------------------------------------

def test_guide_table_needs_core_and_aux_keyword():
    root = _sec(_tbl("작성요령: 항목별로 기재 후 ※삭제 후 제출") + _para("본문"))
    assert remove_form_guides(root) == 1
    assert _texts(root) == ["본문"]


def test_core_keyword_alone_is_not_removed():
    # '작성요령'만 있고 삭제 지시가 없으면 본문일 수 있다 → 보존(오삭제 금지).
    root = _sec(_para("작성요령을 참고하여 기재합니다"))
    assert remove_form_guides(root) == 0
    assert _texts(root) == ["작성요령을 참고하여 기재합니다"]


def test_aux_keyword_alone_is_not_removed():
    root = _sec(_para("도식화 자료를 첨부했습니다"))
    assert remove_form_guides(root) == 0


def test_guide_paragraph_is_removed():
    root = _sec(_para("작성방법 — 도식화 자료 삽입") + _para("본문 유지"))
    assert remove_form_guides(root) == 1
    assert _texts(root) == ["본문 유지"]


def test_guide_table_and_paragraph_counted_together():
    root = _sec(
        _tbl("기재요령 · 유의사항")
        + _para("작성 요령: 자율 변경 가능")
        + _para("제출 본문")
    )
    assert remove_form_guides(root) == 2
    assert _texts(root) == ["제출 본문"]


def test_clean_document_is_untouched():
    root = _sec(_para("성명") + _para("박다솜"))
    before = etree.tostring(root)
    assert remove_form_guides(root) == 0
    assert etree.tostring(root) == before


# --- strip_meta_notes -------------------------------------------------------

def test_meta_lines_starting_with_reference_mark_are_dropped():
    got = strip_meta_notes("첫 줄\n※ 이건 내가 볼 메모\n마지막 줄")
    assert got == "첫 줄\n마지막 줄"


def test_indented_meta_line_is_also_dropped():
    assert strip_meta_notes("   ※ 들여쓴 메모\n본문") == "본문"


def test_writing_attitude_parenthetical_is_removed():
    assert strip_meta_notes("성과를 기술한다(과장 없이 사실만).") == "성과를 기술한다."


def test_ordinary_parenthetical_is_preserved():
    # 일반 괄호(부연 설명)는 본문이므로 지우지 않는다.
    text = "매출 12억원(2025년 기준)을 달성했다."
    assert strip_meta_notes(text) == text


def test_plain_text_passes_through():
    assert strip_meta_notes("평범한 본문") == "평범한 본문"


# --- reformat_bullet_heading ------------------------------------------------

def test_dash_subtitle_is_trimmed():
    assert reformat_bullet_heading("■ 핵심역량 — 문서 자동화") == "■ (핵심역량)"


def test_hyphen_and_en_dash_variants_are_trimmed():
    assert reformat_bullet_heading("■ 핵심역량 - 설명") == "■ (핵심역량)"
    assert reformat_bullet_heading("■ 핵심역량 – 설명") == "■ (핵심역량)"


def test_parenthesised_subtitle_is_trimmed():
    assert reformat_bullet_heading("■ 핵심역량(부제)") == "■ (핵심역량)"


def test_bare_heading_gets_parentheses():
    assert reformat_bullet_heading("■ 핵심역량") == "■ (핵심역량)"


def test_surrounding_whitespace_is_normalized():
    assert reformat_bullet_heading("  ■ 역량 — 설명  ") == "■ (역량)"


def test_non_bullet_line_is_returned_as_is():
    assert reformat_bullet_heading("일반 문장 — 설명") == "일반 문장 — 설명"


def test_reformat_is_idempotent():
    # 이미 '■ (라벨)' 인 줄을 다시 넣어도 라벨이 사라지지 않는다(글자 손실 금지).
    once = reformat_bullet_heading("■ 핵심역량 — 문서 자동화")
    assert reformat_bullet_heading(once) == once == "■ (핵심역량)"


def test_reformat_idempotent_even_with_trailing_subtitle():
    assert reformat_bullet_heading("■ (핵심역량) — 덧붙임") == "■ (핵심역량)"
