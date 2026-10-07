"""test_pure_hwpx_fill_coverage_report.py — 신청서 채움률 리포트 자료구조 안전망.

``hwpx_fill_coverage`` 는 HWPX 신청서를 섹션(인적·학력·자격·경력·모집분야·서명)별로
"몇 칸 채웠고 몇 칸 비었나"로 요약한다. 여기서는 실제 HWPX 를 열지 않고 **집계·요약
자료구조**(SectionCoverage·CoverageReport)와 파일이 없을 때의 안전한 반환만 검증한다.
야간 안전망(2026-08-04).

여기서 고정하는 계약:
- 칸이 하나도 없는 섹션의 채움률은 0으로 나눔이 아니라 0.0 이다(진단이 죽지 않게).
- 리포트 전체 채움률도 섹션이 없을 때 0.0 (분모 0 방지).
- 파일이 없으면 예외가 아니라 ``ok=False`` + 사유로 돌려준다.
"""

from __future__ import annotations

from auto_write.services.hwpx_fill_coverage import (
    CoverageReport,
    SectionCoverage,
    score_hwpx_coverage,
)


# --- SectionCoverage ---------------------------------------------------------

def test_total_and_rate():
    sec = SectionCoverage("인적", filled=3, empty=1)
    assert sec.total == 4
    assert sec.rate == 0.75


def test_rate_is_zero_when_there_is_nothing_to_fill():
    # 칸이 0개인 섹션에서 0으로 나누지 않는다.
    sec = SectionCoverage("모집분야")
    assert sec.total == 0 and sec.rate == 0.0


def test_fully_filled_section_rate_is_one():
    assert SectionCoverage("자격", filled=5).rate == 1.0


def test_section_as_dict_rounds_rate():
    data = SectionCoverage("경력", filled=1, empty=2, notes=["미체크"]).as_dict()
    assert data == {
        "name": "경력", "filled": 1, "empty": 2, "total": 3,
        "rate": 0.333, "notes": ["미체크"],
    }


def test_section_notes_default_to_empty_list():
    assert SectionCoverage("서명").as_dict()["notes"] == []


# --- CoverageReport ----------------------------------------------------------

def test_report_overall_rate_aggregates_sections():
    rep = CoverageReport(
        path="a.hwpx",
        sections=[
            SectionCoverage("인적", filled=3, empty=1),
            SectionCoverage("경력", filled=1, empty=5),
        ],
    )
    data = rep.as_dict()
    assert data["overall_rate"] == 0.4          # (3+1) / (4+6)
    assert [s["name"] for s in data["sections"]] == ["인적", "경력"]
    assert data["ok"] is True


def test_report_without_sections_has_zero_overall_rate():
    # 분모 0 방지 — 진단이 ZeroDivisionError 로 죽지 않는다.
    assert CoverageReport(path="a.hwpx").as_dict()["overall_rate"] == 0.0


def test_report_with_only_empty_sections_is_zero():
    rep = CoverageReport(path="a.hwpx", sections=[SectionCoverage("인적", empty=4)])
    assert rep.as_dict()["overall_rate"] == 0.0


def test_report_as_dict_schema():
    assert set(CoverageReport(path="a.hwpx").as_dict()) == {
        "path", "ok", "sections", "overall_rate", "notes"
    }


# --- score_hwpx_coverage: 입력이 없을 때 -------------------------------------

def test_missing_file_returns_report_instead_of_raising(tmp_path):
    rep = score_hwpx_coverage(tmp_path / "없는파일.hwpx")
    assert rep.ok is False
    assert rep.notes == ["파일 없음"]
    assert rep.sections == []
    assert rep.as_dict()["overall_rate"] == 0.0


def test_directory_path_is_also_treated_as_missing(tmp_path):
    # 폴더를 넘겨도 ZIP 열기로 넘어가지 않고 안전하게 보고한다.
    rep = score_hwpx_coverage(tmp_path)
    assert rep.ok is False and rep.notes == ["파일 없음"]
