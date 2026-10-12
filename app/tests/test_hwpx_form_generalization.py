# -*- coding: utf-8 -*-
"""실양식 5종(킥스업·마켓게이트 v2.2·STAR·은평·수원 멘토) 빈 원본 → 엔진 채움 비교에서 나온 일반 결함.

양식 이름·문구를 코드에 박지 않고, '안내문이 예시색(파랑·빨강·회색)으로 적힌 칸', '한컴 기호 글꼴 빈 체크박스',
'빈 불릿 자리표시자', '자리표시 단어(텍스트)'를 가짜 데이터로 재현해 일반 규칙으로 고쳤음을 확인한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from auto_write.services.hwpx_fill import fill_hwpx
from core.docx.services.hwpx_fill import _cell_has_blue_example_style, _is_example_color, _is_hwpx_guidance_placeholder
from core.docx.services.hwpx_protected_regions import is_value_cell_guidance
from test_hwpx_engine_coverage_synthetic import NS, package, root, table
from test_hwpx_round2_fill import _cell, _row, _run

RED, BLACK = "2", "0"   # 테스트 헤더: charPr 2=#FF0000, 0=#000000, 34=#0000FF


def _texts(path: Path) -> list[str]:
    return ["".join(tc.itertext()) for tc in root(path).xpath("//hp:tc", namespaces=NS)]


def _fill(tmp_path: Path, body: str, identity: dict) -> tuple[Path, Path]:
    src = package(tmp_path, body)
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity=identity)
    return src, out


# ── 예시색 판정 ─────────────────────────────────────────────────
@pytest.mark.parametrize("color,expected", [
    ("#FF0000", True), ("#0000FF", True), ("#0909D9", True), ("#808080", True),
    ("#000000", False), ("#333333", False), ("#FFFFFF", False), ("", False), ("auto", False),
])
def test_example_color_is_saturated_or_mid_gray_only(color, expected):
    assert _is_example_color(color) is expected


# ── 칸 전체가 예시색 안내문 ────────────────────────────────────────
def test_red_instruction_cell_is_replaced_with_value(tmp_path):
    guide = "창업아이템명 기재 (어떤 아이템인지 알 수 있는 명칭사용)"
    _src, out = _fill(tmp_path, table([_row(0, "창업아이템", guide, RED)]), {"창업아이템": "테스트 아이템"})
    cells = _texts(out)
    assert cells[1] == "테스트 아이템"


def test_same_text_in_body_color_is_an_actual_value_and_kept(tmp_path):
    """같은 문장이라도 본문색이면 사용자가 쓴 실값일 수 있다 → 덮어쓰지 않는다(기존 보호 유지)."""
    guide = "창업아이템명 기재 (어떤 아이템인지 알 수 있는 명칭사용)"
    _src, out = _fill(tmp_path, table([_row(0, "창업아이템", guide, BLACK)]), {"창업아이템": "테스트 아이템"})
    assert _texts(out)[1] == guide


def test_example_style_allows_only_symbol_runs_in_body_color(tmp_path):
    """본문색 run 에 글자(한글·영숫자)가 있으면 실값이 섞였을 수 있어 예시체로 보지 않는다."""
    src = package(tmp_path, table([_row(0, "핵심기술", "")]))
    from lxml import etree
    from zipfile import ZipFile
    from core.docx.services.hwpx_fill import _BlackCharPr
    with ZipFile(src) as z:
        black = _BlackCharPr(etree.fromstring(z.read("Contents/header.xml")))
    tc_xml = (
        '<hp:tc xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:subList><hp:p>'
        f'{_run("· ", BLACK)}{_run("핵심기술을 작성", RED)}</hp:p></hp:subList></hp:tc>'
    )
    assert _cell_has_blue_example_style(etree.fromstring(tc_xml), black) is True
    mixed = tc_xml.replace(_run("· ", BLACK), _run("홍길동 ", BLACK))
    assert _cell_has_blue_example_style(etree.fromstring(mixed), black) is False


# ── '라벨: 안내문' 한 줄(접두 라벨은 본문색, 안내문만 예시색) ──────────
def test_inline_prefixed_instruction_keeps_label_and_writes_value(tmp_path):
    runs = _run("전  화: ", BLACK) + _run("통화 가능한 신청인 연락처 기재", RED)
    body = table(["<hp:tr>" + _cell(0, 0, _run("연  락  처", BLACK)) + _cell(1, 0, runs) + "</hp:tr>"])
    _src, out = _fill(tmp_path, body, {"전화": "010-0000-0000"})
    value_cell = _texts(out)[1]
    assert value_cell.startswith("전  화:") and "010-0000-0000" in value_cell
    assert "기재" not in value_cell


# ── 한컴 기호 글꼴 빈 체크박스 ─────────────────────────────────────
def test_symbol_font_empty_box_is_checked_for_matching_option(tmp_path):
    body = table([_row(0, "신청구분", "᥃ 예비창업자    ᥃ 기창업자", BLACK)])
    _src, out = _fill(tmp_path, body, {"신청구분": "예비창업자"})
    cell = _texts(out)[1]
    assert cell.count("■") == 1 and cell.index("■") < cell.index("예비창업자") < cell.index("᥃")


def test_symbol_font_box_not_checked_without_matching_value(tmp_path):
    body = table([_row(0, "신청구분", "᥃ 예비창업자    ᥃ 기창업자", BLACK)])
    _src, out = _fill(tmp_path, body, {"신청구분": "법인사업자"})
    assert "■" not in _texts(out)[1]


# ── 불릿만 반복된 자리표시 칸 · 자리표시 단어 ────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("·\n·\n·", True), ("· · ·", True), ("○ ○", True), ("-", False), ("· 가나다", False),
    ("텍스트", True), ("내용 입력", True), ("텍스트 편집기를 개발", False),
    ("◦ex) 멘토활동 관련", True), ("올해 사업계획서를 작성", False),
])
def test_placeholder_shapes(text, expected):
    assert _is_hwpx_guidance_placeholder(text) is expected
    if expected:
        assert is_value_cell_guidance(text)
    else:
        assert not is_value_cell_guidance(text) or text == "올해 사업계획서를 작성" and False


# ── 세로형 서술 블록(라벨 행 아래 전폭 값 칸) ─────────────────────────
def _vertical_block(pairs):
    rows = []
    for i, (label, value) in enumerate(pairs):
        rows.append("<hp:tr>" + _cell(0, 2 * i, _run(label)) + "</hp:tr>")
        rows.append("<hp:tr>" + _cell(0, 2 * i + 1, _run(value)) + "</hp:tr>")
    return table(rows)


def test_vertical_label_row_above_full_width_value_cell_is_written(tmp_path):
    from test_hwpx_engine_coverage_synthetic import apply
    src = package(tmp_path, _vertical_block([("사업 아이템 소개", "텍스트"), ("프로그램 지원 동기", "텍스트")]))
    original = src.read_bytes()
    out, written, notes, _ = apply(tmp_path, src, {"사업 아이템 소개": "소개 가짜 본문", "프로그램 지원 동기": "동기 가짜 본문"})
    cells = _texts(out)
    assert cells == ["사업 아이템 소개", "소개 가짜 본문", "프로그램 지원 동기", "동기 가짜 본문"]
    assert src.read_bytes() == original and len(written) == 2


def test_vertical_pairing_never_applies_to_multi_column_headers(tmp_path):
    from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
    from core.docx.services.hwpx_protected_regions import authorize_guidance_value_writes
    rows = ["<hp:tr>" + _cell(0, 0, _run("항목")) + _cell(1, 0, _run("값")) + _cell(2, 0, _run("비고")) + "</hp:tr>",
            "<hp:tr>" + _cell(0, 1, _run("텍스트")) + _cell(1, 1, _run("텍스트")) + _cell(2, 1, _run("텍스트")) + "</hp:tr>"]
    src = package(tmp_path, table(rows))
    labels = {g.field_label for g in authorize_guidance_value_writes(index_hwpx_structure(src))}
    assert "비고" not in labels


# ── 유색 '실값'은 보존한다(예시색 규칙의 안전장치) ──────────────────────
def test_red_actual_value_is_preserved_but_red_instruction_is_replaced(tmp_path):
    body = table([_row(0, "상호", "보존기업", RED), _row(1, "창업아이템", "창업아이템명 기재", RED)])
    _src, out = _fill(tmp_path, body, {"상호": "침범", "창업아이템": "테스트 아이템"})
    cells = _texts(out)
    assert cells[1] == "보존기업"          # 빨강이지만 지시문이 아닌 기존 실값
    assert cells[3] == "테스트 아이템"      # 빨강 지시문은 값으로 교체


def test_pure_blue_example_keeps_existing_behavior(tmp_path):
    body = table([_row(0, "대표자", "홍길동", "34")])   # #0000FF 예시체(실값처럼 보여도 예시)
    _src, out = _fill(tmp_path, body, {"대표자": "박다솜"})
    assert _texts(out)[1] == "박다솜"
