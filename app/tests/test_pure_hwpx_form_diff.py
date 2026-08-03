"""test_pure_hwpx_form_diff.py — 원본 양식↔작성본 대조 안전망 (순수 로직).

정부 양식은 **값만 채우고 양식 문구·구조는 그대로** 제출해야 한다(L070).
``compare_hwpx_forms`` 는 두 문서의 글자 목록을 나란히 비교해 '빈칸이 값으로 찬 것'
(정상)과 '양식 문구가 바뀌거나 사라진 것'(결함)을 갈라낸다.

ZIP 을 여는 부분(``_load_section``)만 가짜로 갈아끼우고, 판정 로직은 XML 문자열로
그대로 돌린다 — 실제 HWPX 파일·한글은 쓰지 않는다. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 빈칸 → 값 = ``value_fills``(정상). 값 → 빈칸 = ``form_phrase_drops``(결함).
- 글자가 바뀌면 ``form_phrase_edits``(결함).
- 표·행·칸·문단·체크박스 개수가 하나라도 다르면 ``structure_ok=False``.
- ``form_intact`` 는 이 셋이 모두 깨끗할 때만 True.
"""

from __future__ import annotations

import pytest
from lxml import etree

from auto_write.services import hwpx_form_diff as mod
from auto_write.services.hwpx_form_diff import FormDiffReport, compare_hwpx_forms

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def _doc(*texts: str, tables: int = 1) -> str:
    """hp:t 텍스트 목록과 표 개수를 가진 최소 섹션 XML."""
    body = "".join(f"<p><run><t>{t}</t></run></p>" for t in texts)
    tbl = "<tbl><tr><tc/></tr></tbl>" * tables
    return f'<sec xmlns="{_HP}">{body}{tbl}</sec>'


@pytest.fixture
def compare(monkeypatch):
    """src/dst 자리에 XML 문자열을 바로 넣어 비교하는 헬퍼(ZIP 접근 없음)."""

    def _run(src_xml: str, dst_xml: str):
        roots = {"src": src_xml, "dst": dst_xml}
        monkeypatch.setattr(
            mod,
            "_load_section",
            lambda p: etree.fromstring(roots[str(p)].encode("utf-8")),
        )
        return compare_hwpx_forms("src", "dst")

    return _run


# --- FormDiffReport 자체 ----------------------------------------------------

def test_fresh_report_is_intact():
    rep = FormDiffReport()
    assert rep.form_intact is True
    assert rep.as_dict()["form_intact"] is True


def test_form_intact_is_false_if_any_form_area_changed():
    assert FormDiffReport(form_phrase_edits=1).form_intact is False
    assert FormDiffReport(form_phrase_drops=1).form_intact is False
    assert FormDiffReport(structure_ok=False).form_intact is False
    # 값 채움은 결함이 아니다.
    assert FormDiffReport(value_fills=9).form_intact is True


def test_as_dict_converts_structure_deltas_to_lists():
    rep = FormDiffReport(structure_ok=False, structure_deltas={"표": (2, 1)})
    assert rep.as_dict()["structure_deltas"] == {"표": [2, 1]}


# --- 값 채움(정상) ----------------------------------------------------------

def test_no_change_reports_intact(compare):
    rep = compare(_doc("성명", "박다솜"), _doc("성명", "박다솜"))
    assert rep.form_intact is True
    assert rep.value_fills == 0
    assert rep.form_phrase_edits == 0 and rep.form_phrase_drops == 0
    assert rep.notes == []


def test_blank_filled_with_value_counts_as_value_fill(compare):
    rep = compare(_doc("성명", ""), _doc("성명", "박다솜"))
    assert rep.value_fills == 1
    assert rep.form_intact is True  # 값 채움은 허용


def test_whitespace_only_cell_counts_as_blank(compare):
    # 공백만 든 칸도 '빈칸'으로 본다(양식 문구 삭제로 오판하지 않는다).
    rep = compare(_doc("성명", "   "), _doc("성명", "박다솜"))
    assert rep.value_fills == 1 and rep.form_phrase_edits == 0


# --- 양식 훼손(결함) --------------------------------------------------------

def test_removed_form_phrase_is_a_drop(compare):
    rep = compare(_doc("작성요령", "값"), _doc("", "값"))
    assert rep.form_phrase_drops == 1
    assert rep.form_intact is False
    assert rep.notes and "양식 고유 변경" in rep.notes[0]


def test_edited_form_phrase_is_an_edit(compare):
    rep = compare(_doc("모집분야", "값"), _doc("모집 분야(수정)", "값"))
    assert rep.form_phrase_edits == 1
    assert rep.form_intact is False


def test_edit_ignores_only_surrounding_whitespace(compare):
    # 앞뒤 공백만 다른 것은 문구 변경으로 세지 않는다(오탐 0).
    rep = compare(_doc("모집분야"), _doc("  모집분야  "))
    assert rep.form_phrase_edits == 0 and rep.form_intact is True


# --- 구조 변화 --------------------------------------------------------------

def test_missing_table_breaks_structure(compare):
    rep = compare(_doc("성명", tables=2), _doc("성명", tables=1))
    assert rep.structure_ok is False
    assert rep.structure_deltas["표"] == (2, 1)
    assert rep.form_intact is False


def test_structure_delta_records_every_changed_counter(compare):
    rep = compare(_doc("가", "나", tables=1), _doc("가", tables=1))
    # 문단이 하나 사라졌다 → 문단 카운터가 델타에 남는다.
    assert "문단" in rep.structure_deltas
    assert rep.structure_deltas["문단"] == (2, 1)


def test_checkbox_count_change_is_detected(compare):
    src = f'<sec xmlns="{_HP}"><p><run><checkBtn/></run></p></sec>'
    dst = f'<sec xmlns="{_HP}"><p><run/></p></sec>'
    rep = compare(src, dst)
    assert rep.structure_deltas["체크박스"] == (1, 0)
    assert rep.form_intact is False


def test_as_dict_of_real_comparison_has_expected_keys(compare):
    data = compare(_doc("성명", ""), _doc("성명", "박다솜")).as_dict()
    assert set(data) == {
        "structure_ok",
        "form_intact",
        "form_phrase_edits",
        "form_phrase_drops",
        "value_fills",
        "structure_deltas",
        "notes",
    }
    assert data["value_fills"] == 1
