"""test_pure_hwpx_section_split.py — secPr 첫 문단 재활용 안전망 (순수 함수).

공고 본문을 떼어 '서식만' 남길 때, 용지·여백 설정(secPr)이 들어 있는 첫 문단을
통째로 지우면 한글이 기본 여백으로 되돌려 **표가 잘린다**(실측 교훈 L089). 그래서
첫 문단은 삭제하지 않고 '내용만 비워' 재활용한다. 이 모듈은 lxml 트리만 받는
순수 로직이라 파일·한글 없이 검증한다. 야간 안전망(2026-08-04).

여기서 고정하는 계약:
- secPr 노드는 살아남고, 같은 문단의 다른 내용(글자 run)만 사라진다.
- 용지·여백 값(pagePr/margin)은 스냅샷으로 남겨 왕복 후 대조할 수 있다.
- secPr 가 없으면 아무것도 건드리지 않고 notes 로 알린다(무리한 수정 금지).
"""

from __future__ import annotations

from lxml import etree

from auto_write.services.hwpx_section_split import (
    assert_pagepr_unchanged,
    find_first_secpr_paragraph,
    find_leading_page_break,
    find_page_break_paragraphs,
    recycle_first_secpr_paragraph,
    remove_leading_page_break,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

# 실 HWPX 와 동일하게 hp 기본 네임스페이스를 달아 _q("p") 경로를 그대로 탄다.
_SECPR = (
    "<run><secPr>"
    '<pagePr width="59528" height="84188" landscape="WIDELY">'
    '<margin left="8504" right="8504" top="5668" bottom="4252"/>'
    "</pagePr>"
    "</secPr></run>"
)


def _sec(body: str):
    return etree.fromstring(
        f'<sec xmlns="{_HP}">{body}</sec>'.encode("utf-8")
    )


def _text(el) -> str:
    return "".join(t.text or "" for t in el.iter(f"{{{_HP}}}t"))


def _with_secpr():
    return _sec(
        f"<p>{_SECPR}<run><t>공고 본문 — 모집요강</t></run></p>"
        "<p><run><t>다음 문단</t></run></p>"
    )


# --- find_first_secpr_paragraph ---------------------------------------------

def test_find_returns_none_when_no_secpr():
    assert find_first_secpr_paragraph(_sec("<p><run><t>본문</t></run></p>")) is None


def test_find_returns_the_first_paragraph_holding_secpr():
    root = _sec(f"<p><run><t>앞</t></run></p><p>{_SECPR}</p>")
    p = find_first_secpr_paragraph(root)
    assert p is not None
    assert p is list(root)[1]


# --- recycle_first_secpr_paragraph ------------------------------------------

def test_recycle_keeps_paragraph_and_drops_only_its_content():
    root = _with_secpr()
    first = list(root)[0]
    out = recycle_first_secpr_paragraph(root)

    assert out["ok"] is True and out["recycled"] is True and out["had_secpr"] is True
    # 문단 자체는 살아 있다(삭제하면 여백이 초기화된다).
    assert list(root)[0] is first
    # 내용은 비었고, 남은 자식은 secPr 하나뿐.
    assert _text(first) == ""
    assert len(first) == 1
    assert etree.QName(first[0]).localname == "secPr"
    # 뒤 문단은 건드리지 않는다.
    assert _text(list(root)[1]) == "다음 문단"


def test_recycle_snapshots_page_and_margin_values():
    out = recycle_first_secpr_paragraph(_with_secpr())
    snap = out["page_pr_snapshot"]
    assert snap["pagePr.width"] == "59528"
    assert snap["pagePr.height"] == "84188"
    assert snap["margin.left"] == "8504"
    assert snap["margin.bottom"] == "4252"


def test_recycle_is_noop_without_secpr():
    root = _sec("<p><run><t>본문</t></run></p>")
    before = etree.tostring(root)
    out = recycle_first_secpr_paragraph(root)

    assert out["ok"] is False and out["recycled"] is False and out["had_secpr"] is False
    assert out["page_pr_snapshot"] == {}
    assert out["notes"] and "secPr" in out["notes"][0]
    assert etree.tostring(root) == before  # 트리 무변경


def test_recycle_when_secpr_is_already_a_direct_child():
    root = _sec(
        "<p><secPr><pagePr width='1'/></secPr><run><t>지워질 글</t></run></p>"
    )
    out = recycle_first_secpr_paragraph(root)
    p = list(root)[0]
    assert out["recycled"] is True
    assert len(p) == 1 and etree.QName(p[0]).localname == "secPr"
    assert _text(p) == ""


def test_recycle_twice_is_idempotent():
    root = _with_secpr()
    first = recycle_first_secpr_paragraph(root)
    second = recycle_first_secpr_paragraph(root)
    assert second["recycled"] is True
    assert second["page_pr_snapshot"] == first["page_pr_snapshot"]
    assert len(list(root)[0]) == 1


# --- assert_pagepr_unchanged ------------------------------------------------

def test_assert_reports_nothing_when_values_survive():
    root = _with_secpr()
    snap = recycle_first_secpr_paragraph(root)["page_pr_snapshot"]
    assert assert_pagepr_unchanged(snap, root) == []


def test_assert_reports_changed_margin():
    root = _with_secpr()
    snap = recycle_first_secpr_paragraph(root)["page_pr_snapshot"]
    # 왕복 중 여백이 기본값으로 되돌아간 상황을 흉내낸다.
    for el in root.iter(f"{{{_HP}}}margin"):
        el.set("left", "0")
    bad = assert_pagepr_unchanged(snap, root)
    assert len(bad) == 1
    assert "margin.left" in bad[0] and "'8504'" in bad[0]


def test_assert_reports_lost_paragraph():
    root = _with_secpr()
    snap = recycle_first_secpr_paragraph(root)["page_pr_snapshot"]
    p = find_first_secpr_paragraph(root)
    p.getparent().remove(p)
    assert assert_pagepr_unchanged(snap, root) == ["secPr 문단 소실"]


def test_assert_with_empty_snapshot_passes():
    # 대조할 기준이 없으면 위반도 없다(스냅샷 없는 경로에서 오탐 방지).
    assert assert_pagepr_unchanged({}, _with_secpr()) == []


# --- 선두 쪽나눔 제거(L090) --------------------------------------------------
# 공고 본문을 떼어내고 나면 남은 '[서식 1]' 문단이 쪽나눔을 달고 있어 빈 첫 페이지가
# 생긴다. pageBreak 속성을 0 으로 바꾸는 것만으로는 한글이 열 때 되살려 소용이 없으므로
# (실측 L090), secPr 문단에 내용을 옮겨 담고 원래 문단을 '구조적으로' 없앤다.

def _split_leftover():
    """본문을 떼어낸 직후 상태 — 첫 문단은 secPr 만 남은 빈 문단, 그 다음이 쪽나눔 서식."""
    return _sec(
        f"<p>{_SECPR}</p>"
        '<p pageBreak="1" paraPrIDRef="7" styleIDRef="3">'
        "<run><t>[서식 1]</t></run></p>"
        "<p><run><t>전문상담위원 참여 신청서</t></run></p>"
    )


def test_find_page_break_paragraphs_lists_indices():
    root = _split_leftover()
    assert find_page_break_paragraphs(root) == [1]


def test_find_leading_page_break_when_only_empty_paragraphs_precede():
    assert find_leading_page_break(_split_leftover()) == 1


def test_find_leading_page_break_ignores_intentional_break_after_content():
    # 앞에 실제 내용이 있으면 의도된 페이지 구분이다 — 건드리면 안 된다.
    root = _sec(
        f"<p>{_SECPR}<run><t>1쪽 본문</t></run></p>"
        '<p pageBreak="1"><run><t>2쪽 제목</t></run></p>'
    )
    assert find_page_break_paragraphs(root) == [1]
    assert find_leading_page_break(root) == -1


def test_remove_leading_page_break_moves_content_onto_secpr_paragraph():
    root = _split_leftover()
    head = list(root)[0]
    out = remove_leading_page_break(root)

    assert out["ok"] is True and out["removed"] is True
    assert out["donor_index"] == 1 and out["paragraphs_removed"] == 1
    # 문단이 하나 줄었고(구조적 제거), secPr 문단은 그대로 살아 있다.
    tops = list(root)
    assert len(tops) == 2 and tops[0] is head
    # 서식 문단의 글과 서식 참조가 secPr 문단으로 넘어왔다.
    assert _text(head) == "[서식 1]"
    assert head.get("paraPrIDRef") == "7" and head.get("styleIDRef") == "3"
    # secPr 는 보존 — 여백이 기본값으로 돌아가지 않는다(L089).
    assert find_first_secpr_paragraph(root) is head


def test_remove_leading_page_break_keeps_margins():
    root = _split_leftover()
    snap = {"pagePr.width": "59528", "margin.left": "8504"}
    remove_leading_page_break(root)
    assert assert_pagepr_unchanged(snap, root) == []


def test_remove_leading_page_break_leaves_no_leading_break():
    root = _split_leftover()
    remove_leading_page_break(root)
    # 빈 첫 페이지의 원인이 사라졌다 — 속성이 아니라 문단 구조로.
    assert find_leading_page_break(root) == -1


def test_remove_leading_page_break_is_idempotent():
    root = _split_leftover()
    remove_leading_page_break(root)
    before = etree.tostring(root)
    out = remove_leading_page_break(root)
    assert out["removed"] is False and out["paragraphs_removed"] == 0
    assert etree.tostring(root) == before


def test_remove_leading_page_break_noop_without_break():
    root = _with_secpr()
    before = etree.tostring(root)
    out = remove_leading_page_break(root)
    assert out["removed"] is False and out["donor_index"] == -1
    assert etree.tostring(root) == before


def test_remove_leading_page_break_degrades_honestly_when_secpr_is_the_break():
    # secPr 문단 자체가 쪽나눔이면 옮겨 담을 그릇이 없다 — 문단을 지우면 여백이 날아간다.
    # 속성만 끄고, 사람이 재확인하도록 notes 로 알린다(조용한 실패 금지).
    root = _sec(f'<p pageBreak="1">{_SECPR}</p><p><run><t>본문</t></run></p>')
    out = remove_leading_page_break(root)
    assert out["removed"] is True and out["paragraphs_removed"] == 0
    assert out["notes"] and "L090" in out["notes"][0]
    assert find_first_secpr_paragraph(root) is list(root)[0]
