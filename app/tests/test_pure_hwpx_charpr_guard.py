"""test_pure_hwpx_charpr_guard.py — charPr append-only 불변 검사 안전망 (순수 함수).

한글 문서의 글자서식(charPr)은 header.xml 목록에 **끝에만 덧붙여야** 한다. 중간에
끼워 넣으면 id 와 자식 순서가 어긋나 한글이 엉뚱한 서식을 참조한다(실측 교훈 L076).
``check_charpr_append_only`` 는 lxml 트리만 받는 순수 검사라 파일·한글 없이 검증한다.
야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 위반이 없으면 빈 목록(= OK). 검사기는 문서를 절대 고치지 않는다.
- 숫자 id 가 문서 순서대로 비감소면 통과(같은 id 반복 허용).
- 뒤에 더 작은 id 가 나오거나, 부모 안 마지막 항목이 최대 id 가 아니면 위반.
- id 가 숫자가 아니면 판단을 보류하고 통과시킨다(다른 체계를 오탐하지 않음).
"""

from __future__ import annotations

import pytest
from lxml import etree

from auto_write.services.hwpx_charpr_guard import (
    assert_charpr_append_only,
    check_charpr_append_only,
    iter_charpr_elements,
)

# 이 검사는 local-name 만 보므로 네임스페이스 없이 작성해도 실 HWPX 와 같은 경로를 탄다.


def _root(xml: str):
    return etree.fromstring(xml.encode("utf-8"))


def _charprs(*ids: str) -> str:
    return "".join(f'<charPr id="{i}"/>' for i in ids)


# --- iter_charpr_elements ---------------------------------------------------

def test_iter_returns_empty_for_none_root():
    # header 를 못 읽은 경우에도 검사기가 죽지 않는다.
    assert iter_charpr_elements(None) == []


def test_iter_collects_only_charpr_with_id_in_document_order():
    root = _root(
        "<head><refList>"
        '<charPr id="0"/><fontface id="9"/><charPr id="1"/>'
        "<charPr/>"          # id 없음 — 대상 아님
        '<charPr id=""/>'    # 빈 id — 대상 아님
        "</refList></head>"
    )
    got = [el.get("id") for el in iter_charpr_elements(root)]
    assert got == ["0", "1"]


def test_iter_finds_nested_charpr():
    root = _root('<head><a><b><charPr id="7"/></b></a></head>')
    assert [el.get("id") for el in iter_charpr_elements(root)] == ["7"]


# --- 통과 케이스 -------------------------------------------------------------

def test_no_charpr_is_ok():
    assert check_charpr_append_only(_root("<head/>")) == []


def test_ascending_ids_pass():
    root = _root(f"<head><refList>{_charprs('0', '1', '2', '3')}</refList></head>")
    assert check_charpr_append_only(root) == []


def test_appended_clone_at_end_passes():
    # 검정 클론을 목록 '끝'에 붙인 정상 케이스(L076 이 요구하는 방식).
    root = _root(f"<head><refList>{_charprs('0', '1', '2')}</refList></head>")
    etree.SubElement(root.find("refList"), "charPr", id="3")
    assert check_charpr_append_only(root) == []


def test_clone_inserted_in_the_middle_is_caught():
    # 같은 클론을 '중간'에 끼워 넣으면 검출된다(append 와 insert 의 차이).
    root = _root(f"<head><refList>{_charprs('0', '1', '2')}</refList></head>")
    ref = root.find("refList")
    ref.insert(1, etree.Element("charPr", id="3"))
    assert check_charpr_append_only(root) != []


def test_repeated_ids_are_not_decreasing():
    # 비감소이므로 위반 아님(같은 id 가 이어지는 것은 허용).
    root = _root(f"<head><refList>{_charprs('1', '1', '2')}</refList></head>")
    assert check_charpr_append_only(root) == []


def test_non_numeric_ids_are_skipped_conservatively():
    # 다른 id 체계(문자열)를 쓰는 문서를 오탐으로 막지 않는다.
    root = _root(f"<head><refList>{_charprs('b', 'a')}</refList></head>")
    assert check_charpr_append_only(root) == []


def test_single_numeric_id_per_parent_is_ok():
    # 부모별 '마지막==최대' 검사는 항목이 1개뿐인 그룹을 건너뛴다.
    # (문서 순서 비감소는 부모를 가로질러 계속 지켜져야 한다 — 2 다음 5.)
    root = _root(
        f'<head><a>{_charprs("2")}</a><b>{_charprs("5")}</b></head>'
    )
    assert check_charpr_append_only(root) == []


def test_document_order_is_checked_across_parents():
    # 부모가 달라도 문서 순서가 역행하면(5 → 2) 중간 삽입으로 본다.
    root = _root(
        f'<head><a>{_charprs("5")}</a><b>{_charprs("2")}</b></head>'
    )
    assert any("중간 삽입 의심" in m for m in check_charpr_append_only(root))


# --- 위반 검출 ---------------------------------------------------------------

def test_descending_id_is_reported_as_mid_insert():
    root = _root(f"<head><refList>{_charprs('0', '5', '3')}</refList></head>")
    bad = check_charpr_append_only(root)
    assert any("중간 삽입 의심" in m for m in bad)


def test_mid_insert_reports_both_order_and_append_only():
    # 1,3,2 → ①순서 역행 ②부모 마지막이 최대 id 아님, 두 가지 모두 검출.
    root = _root(f"<head><refList>{_charprs('1', '3', '2')}</refList></head>")
    bad = check_charpr_append_only(root)
    assert len(bad) == 2
    assert any("중간 삽입 의심" in m for m in bad)
    assert any("append-only 위반" in m for m in bad)


def test_separate_parents_each_ending_at_their_max_pass():
    # 부모가 여럿이어도 각 그룹의 마지막이 그 그룹의 최대면 통과.
    root = _root(
        f'<head><a>{_charprs("1", "9")}</a><b>{_charprs("9", "9")}</b></head>'
    )
    assert check_charpr_append_only(root) == []


def test_numeric_and_text_ids_mixed_only_numeric_judged():
    # 문자 id 는 건너뛰고 숫자 id 수열(3→1)만 위반으로 본다.
    root = _root(f"<head><refList>{_charprs('3', 'zz', '1')}</refList></head>")
    bad = check_charpr_append_only(root)
    assert any("중간 삽입 의심" in m for m in bad)


# --- assert 래퍼 -------------------------------------------------------------

def test_assert_passes_silently_when_ok():
    assert assert_charpr_append_only(_root(f"<head>{_charprs('0', '1')}</head>")) is None


def test_assert_raises_with_l076_marker():
    root = _root(f"<head><refList>{_charprs('4', '2')}</refList></head>")
    with pytest.raises(ValueError) as exc:
        assert_charpr_append_only(root)
    assert "L076" in str(exc.value)
