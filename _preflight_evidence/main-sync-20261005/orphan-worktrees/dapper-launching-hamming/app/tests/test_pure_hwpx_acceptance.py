"""test_pure_hwpx_acceptance.py — HWPX 직접 수용검사(변환 없는 XML 점검) 안전망.

hwpx_acceptance 는 HWPX(ZIP/OWPML)를 변환 없이 열어 유색 charPr·양식 안내문구·
linesegarray(줄위치 캐시)를 '개수만' 센다. 카운트 함수는 lxml 루트를 받는 순수
로직이라 XML 문자열로 직접 검증하고, run_hwpx_acceptance 는 tmp_path 안의 작은
ZIP 으로만 돌린다(실 HWP/COM 불사용, 원본 미수정). 야간 안전망(2026-07-16).

여기서 고정하는 계약:
- 유색 판정은 정규 6자리 hex 만 — none/auto/미지정/흰·검정은 세지 않는다(오탐 0).
- 안내문구는 핵심(작성요령 등)+보조(삭제 후 제출 등) **동시** 충족만, 안내 표 안
  단락은 이중 카운트하지 않는다.
- ok = colored·guides·linesegarray 셋 다 0. 판정만 하고 문서는 절대 수정하지 않는다.
"""

from __future__ import annotations

import zipfile

import pytest
from lxml import etree

from auto_write.services.hwpx_acceptance import (
    HwpxAcceptanceReport,
    count_colored_charpr,
    count_form_guides,
    count_linesegarray,
    run_hwpx_acceptance,
)

# 판정 로직은 local-name 만 보므로(네임스페이스 접두어 무시) 테스트 XML 은
# 접두어 없이 작성해도 실 HWPX 와 같은 경로를 탄다.


def _root(xml: str):
    return etree.fromstring(xml.encode("utf-8"))


# --- count_colored_charpr ---------------------------------------------------------

def test_colored_counts_only_regular_hex_non_bw():
    root = _root(
        "<head>"
        '<charPr textColor="FF0000"/>'      # 빨강 — 유색
        '<charPr textColor="#0000ff"/>'     # 소문자+#접두 — 유색(정규화 후 판정)
        '<charPr textColor="000000"/>'      # 검정 — 제외
        '<charPr textColor="FFFFFF"/>'      # 흰색 — 제외
        '<charPr textColor="none"/>'        # 기본색 — 제외
        '<charPr textColor="auto"/>'        # 기본색 — 제외
        '<charPr textColor="FFF"/>'         # 비정형(3자리) — 제외(오탐 0)
        "<charPr/>"                          # 미지정 — 제외
        "</head>")
    n, samples = count_colored_charpr(root)
    assert n == 2
    assert samples == ["#FF0000", "#0000FF"]


def test_colored_samples_capped_at_five():
    body = "".join(f'<charPr textColor="{i:06X}"/>' for i in range(1, 9))  # 유색 8개
    n, samples = count_colored_charpr(_root(f"<head>{body}</head>"))
    assert n == 8 and len(samples) == 5


# --- count_form_guides --------------------------------------------------------------

def test_guide_needs_core_and_aux_together():
    # 핵심(작성요령)만 있는 단락은 본문일 수 있어 세지 않는다 — 동시 충족만 카운트.
    root = _root(
        "<sec>"
        "<p><t>작성요령을 잘 따르십시오</t></p>"
        "<p><t>본 항목은 삭제 후 제출</t></p>"
        "<p><t>작성요령: 이 표는 삭제 후 제출하세요</t></p>"
        "</sec>")
    n, samples = count_form_guides(root)
    assert n == 1
    assert "삭제 후 제출" in samples[0]


def test_guide_table_counted_once_without_inner_paragraph_double_count():
    # 안내 표 1개(안 단락 포함) + 독립 안내 단락 1개 = 2건. 표 안 단락은 중복 제외.
    root = _root(
        "<sec>"
        "<tbl><tr><tc>"
        "<p><t>작성방법 안내</t></p>"
        "<p><t>확인 후 삭제 후 제출</t></p>"     # 핵심·보조가 셀 단락에 흩어져도 표 1건
        "</tc></tr></tbl>"
        "<p><t>기재요령 — 유의사항 포함</t></p>"
        "<p><t>일반 본문 문단</t></p>"
        "</sec>")
    n, _ = count_form_guides(root)
    assert n == 2


def test_no_guides_in_plain_body():
    n, samples = count_form_guides(_root("<sec><p><t>사업 개요 본문</t></p></sec>"))
    assert n == 0 and samples == []


# --- count_linesegarray ---------------------------------------------------------------

def test_linesegarray_counted():
    root = _root("<sec><p><linesegarray/></p><p><linesegarray/></p><p/></sec>")
    assert count_linesegarray(root) == 2
    assert count_linesegarray(_root("<sec><p/></sec>")) == 0


# --- HwpxAcceptanceReport 판정 ----------------------------------------------------------

def test_report_ok_only_when_all_zero():
    clean = HwpxAcceptanceReport(source="a.hwpx")
    assert clean.ok is True and clean.verdict == "제출가능" and clean.fail_defects == 0

    dirty = HwpxAcceptanceReport(source="a.hwpx", colored=1, guides=2, linesegarray=3)
    assert dirty.ok is False and dirty.fail_defects == 6
    assert dirty.verdict == "제출불가(후처리 필요)"
    d = dirty.as_dict()
    assert d["ok"] is False and d["fail_defects"] == 6 and d["colored"] == 1


# --- run_hwpx_acceptance (tmp ZIP 만 사용 — 실 문서·COM 없음) ---------------------------

def _make_hwpx(path, entries: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for name, xml in entries.items():
            z.writestr(name, xml)


def test_run_counts_defects_from_zip(tmp_path):
    src = tmp_path / "산출물.hwpx"
    _make_hwpx(src, {
        "Contents/header.xml": '<head><charPr textColor="FF0000"/></head>',
        "Contents/section0.xml": (
            "<sec><p><t>작성요령 — 삭제 후 제출</t></p>"
            "<p><linesegarray/></p></sec>"),
    })
    rep = run_hwpx_acceptance(src)
    assert (rep.colored, rep.guides, rep.linesegarray) == (1, 1, 1)
    assert rep.ok is False
    assert src.exists()                              # 읽기 전용 — 원본 그대로


def test_run_clean_hwpx_is_ok(tmp_path):
    src = tmp_path / "깨끗.hwpx"
    _make_hwpx(src, {
        "Contents/header.xml": '<head><charPr textColor="000000"/></head>',
        "Contents/section0.xml": "<sec><p><t>본문</t></p></sec>",
    })
    rep = run_hwpx_acceptance(src)
    assert rep.ok is True and rep.verdict == "제출가능"


def test_run_missing_header_notes_and_continues(tmp_path):
    src = tmp_path / "헤더없음.hwpx"
    _make_hwpx(src, {"Contents/section0.xml": "<sec/>"})
    rep = run_hwpx_acceptance(src)
    assert any("header.xml" in n for n in rep.notes)  # 점검 생략을 정직하게 기록
    assert rep.colored == 0


def test_run_rejects_missing_and_non_zip(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_hwpx_acceptance(tmp_path / "없음.hwpx")
    bad = tmp_path / "가짜.hwpx"
    bad.write_bytes(b"not a zip at all")
    with pytest.raises(ValueError):
        run_hwpx_acceptance(bad)
