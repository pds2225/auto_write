"""test_pure_d_trigger.py — C(칸 채우기) 후 D(서술 작성) 대상 판정 순수 로직 안전망.

d_trigger 는 "미매칭 타깃 ∩ 서술형(narrative) 양식 항목"만 bizplan(D 단계) 대상으로
고른다. 파일을 여는 analyze_form 만 가짜로 바꾸고(monkeypatch), 나머지 판정 로직은
전부 순수라 그대로 검증한다. 야간 안전망(2026-07-16).
"""

from __future__ import annotations

from auto_write.services import d_trigger
from auto_write.services.d_trigger import (
    _label_of,
    _labels_match,
    filter_narrative_unmatched,
    narrative_labels_from_form,
    should_run_bizplan_for_target,
)
from auto_write.services.form_analyzer import FormReport


def _report(**kw) -> FormReport:
    return FormReport(template_name="t", source_docx="t.docx", **kw)


# --- narrative_labels_from_form -------------------------------------------------

def test_narrative_labels_from_details_and_items():
    rep = _report(
        writable_item_details=[
            {"label": "사업 추진 계획", "field_kind": "narrative"},
            {"label": "기업명", "field_kind": "fact"},        # 사실칸 — 제외
            {"label": "", "field_kind": "narrative"},          # 빈 라벨 — 제외
        ],
        # writable_items 는 "[필수] " 접두를 벗기고 classify_field_kind 로 재분류
        writable_items=["[필수] 시장 진입 전략", "기업명"],
    )
    labels = narrative_labels_from_form(rep)
    assert labels == {"사업 추진 계획", "시장 진입 전략"}


def test_narrative_labels_empty_form_returns_empty_set():
    assert narrative_labels_from_form(_report()) == set()


# --- _label_of / _labels_match --------------------------------------------------

def test_label_of_priority_target_label_first():
    assert _label_of({"target_label": "A", "normalized": "B", "label": "C"}) == "A"
    assert _label_of({"normalized": "B", "label": "C"}) == "B"
    assert _label_of({"label": " C "}) == "C"
    assert _label_of({}) == ""


def test_labels_match_exact_substring_case():
    assert _labels_match("사업 추진 계획", "사업 추진 계획") is True
    assert _labels_match("추진 계획", "사업 추진 계획") is True     # 부분문자열(양방향)
    assert _labels_match("사업 추진 계획", "추진 계획") is True
    assert _labels_match("PSST 전략", "psst 전략") is True          # 대소문자 무시
    assert _labels_match("팀 구성", "시장 분석") is False
    assert _labels_match("", "사업 추진 계획") is False              # 빈 라벨은 불일치
    assert _labels_match("사업 추진 계획", "") is False


# --- filter_narrative_unmatched -------------------------------------------------

def test_filter_keeps_only_narrative_gaps():
    rep = _report(
        writable_item_details=[
            {"label": "사업 추진 계획", "field_kind": "narrative"},
            {"label": "시장 진입 전략", "field_kind": "narrative"},
        ],
    )
    unmatched = [
        {"target_label": "사업 추진 계획"},          # 서술형 — 대상
        {"normalized": "기업명"},                    # 사실칸 — 제외
        {"label": "시장 진입 전략 상세"},            # 서술 라벨의 확장 표기 — 대상
    ]
    got = filter_narrative_unmatched(unmatched, rep)
    assert got == [unmatched[0], unmatched[2]]


def test_filter_no_narrative_labels_returns_empty():
    # 서술형 항목이 하나도 없는 양식이면 어떤 미매칭도 D 대상이 아니다.
    rep = _report(writable_item_details=[{"label": "기업명", "field_kind": "fact"}])
    assert filter_narrative_unmatched([{"target_label": "사업 추진 계획"}], rep) == []


def test_filter_empty_unmatched_returns_empty():
    rep = _report(writable_item_details=[{"label": "사업 개요", "field_kind": "narrative"}])
    assert filter_narrative_unmatched([], rep) == []


# --- should_run_bizplan_for_target (analyze_form 만 가짜) ------------------------

def test_should_run_bizplan_true_when_narrative_gap(monkeypatch):
    rep = _report(writable_item_details=[{"label": "사업 개요", "field_kind": "narrative"}])
    monkeypatch.setattr(d_trigger, "analyze_form", lambda p: rep)
    run, gaps, form_report = should_run_bizplan_for_target(
        "아무양식.docx", [{"target_label": "사업 개요"}],
    )
    assert run is True
    assert gaps == [{"target_label": "사업 개요"}]
    assert form_report is rep


def test_should_run_bizplan_false_when_no_gap(monkeypatch):
    rep = _report(writable_item_details=[{"label": "사업 개요", "field_kind": "narrative"}])
    monkeypatch.setattr(d_trigger, "analyze_form", lambda p: rep)
    run, gaps, _ = should_run_bizplan_for_target("아무양식.docx", [{"label": "기업명"}])
    assert run is False
    assert gaps == []
