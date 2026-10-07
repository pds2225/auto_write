# -*- coding: utf-8 -*-
"""L규칙 3단계 판정(해당 → 채움 → 통과) 회귀 + form_diff 체크박스 오탐 회귀.

마포형 신청서 구조(라벨/값칸 표·반복 표·선택칸·괄호 안내문)를 **가짜 데이터**로 흉내 낸
합성 HWPX 만 쓴다. 실제 개인정보·원본 양식은 저장소에 넣지 않는다.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from auto_write.domains.domain_classifier import Domain
from auto_write.services.hwpx_form_diff import compare_hwpx_forms
from auto_write.services.lrule_enforcer import enforce_lrules, rule_code
from auto_write.services.lrule_fill_check import inspect_fill
from auto_write.services.lrule_guards import build_lrule_guards

_NS = (
    'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
    'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" '
    'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
)
_HEADER = f'<?xml version="1.0" encoding="UTF-8"?><hh:head {_NS}><hh:refList/></hh:head>'


def _cell(text: str, r: int, c: int) -> str:
    run = f"<hp:run><hp:t>{text}</hp:t></hp:run>" if text else "<hp:run/>"
    return (
        f"<hp:tc><hp:subList><hp:p>{run}</hp:p></hp:subList>"
        f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="1" rowSpan="1"/></hp:tc>'
    )


def _table(rows: list[list[str]]) -> str:
    body = "".join(
        "<hp:tr>" + "".join(_cell(t, r, c) for c, t in enumerate(row)) + "</hp:tr>"
        for r, row in enumerate(rows)
    )
    return f"<hp:p><hp:run><hp:tbl>{body}</hp:tbl></hp:run></hp:p>"


def _hwpx(path: Path, *tables: list[list[str]]) -> Path:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {_NS}>'
        + "".join(_table(t) for t in tables)
        + "</hs:sec>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("Contents/header.xml", _HEADER)
        z.writestr("Contents/section0.xml", section)
    return path


# 마포형: 라벨/값칸 · 종업원수 반복 표 · 선택칸
_PROFILE = [["성명", "가짜이름", "연락처", "010-0000-0000"], ["회사명", "가짜상사", "대표자", "가짜대표"]]
_STAFF_FILLED = [["구분", "2024년", "2025년"], ["상시근로자", "3", "4"], ["단시간근로자", "1", "2"], ["합계", "4", "6"]]
_CHOICE_FILLED = [["사업자 형태", "■ 개인 □ 법인"]]


def _judge(path: Path, domain: Domain = Domain.CONSULTANT_APPLICATION):
    return enforce_lrules(domain, "application_form", path, guards=build_lrule_guards(path))


def _rule(report, code: str) -> dict:
    return next(r for r in report.rules if rule_code(r["id"]) == code)


# ── 채움 단계 ────────────────────────────────────────────────────────────────

def test_all_filled_form_passes_fill_stage(tmp_path):
    path = _hwpx(tmp_path / "ok.hwpx", _PROFILE, _STAFF_FILLED, _CHOICE_FILLED)
    assert inspect_fill(path).findings == []
    report = _judge(path)
    for code in ("L053", "L025", "L034", "L052", "L086"):
        entry = _rule(report, code)
        assert entry["filled"] is True, code
        assert entry["status"] == "PASS" and entry["passed"] is True, code
    assert report.summary["fill_required"] >= 5
    assert report.summary["filled"] == report.summary["fill_required"]


def test_blank_value_cell_fails_with_location(tmp_path):
    profile = [["성명", "가짜이름", "연락처", ""], ["회사명", "가짜상사", "대표자", "가짜대표"]]
    path = _hwpx(tmp_path / "blank.hwpx", profile, _STAFF_FILLED, _CHOICE_FILLED)
    entry = _rule(_judge(path), "L053")
    assert entry["status"] == "FAIL" and entry["filled"] is False and entry["passed"] is False
    assert "blank" in entry["evidence"] and "1행 4열" in entry["location"]


def test_whitespace_only_cell_is_blank(tmp_path):
    profile = [["성명", "가짜이름", "연락처", "  　 "]]
    findings = inspect_fill(_hwpx(tmp_path / "ws.hwpx", profile)).findings
    assert [f.kind for f in findings] == ["blank"]


def test_residual_instruction_text_fails(tmp_path):
    profile = [["성명", "가짜이름"], ["법인등록번호", "(법인사업자 해당 시에만 기재)"]]
    path = _hwpx(tmp_path / "instr.hwpx", profile, _STAFF_FILLED, _CHOICE_FILLED)
    report = _judge(path)
    for code in ("L012", "L053"):
        entry = _rule(report, code)
        assert entry["status"] == "FAIL" and entry["filled"] is False, code
        assert "instruction" in entry["evidence"], code


def test_repeat_rows_filled_only_once_fails(tmp_path):
    staff = [["구분", "2024년", "2025년"], ["상시근로자", "3", "4"], ["단시간근로자", "", ""], ["합계", "", ""]]
    path = _hwpx(tmp_path / "repeat.hwpx", _PROFILE, staff, _CHOICE_FILLED)
    findings = inspect_fill(path).findings
    assert {f.kind for f in findings} == {"repeat_partial"}
    assert len(findings) == 4  # 3·4행 × 2·3열
    entry = _rule(_judge(path), "L053")
    assert entry["status"] == "FAIL" and "repeat_partial" in entry["evidence"]


def test_unselected_choice_fails_checkbox_rules(tmp_path):
    path = _hwpx(tmp_path / "choice.hwpx", _PROFILE, _STAFF_FILLED, [["사업자 형태", "□ 개인 □ 법인"]])
    report = _judge(path)
    for code in ("L025", "L034", "L052", "L086"):
        assert _rule(report, code)["status"] == "FAIL", code


def test_choice_group_split_across_cells_is_not_unchecked(tmp_path):
    """'■ 예비창업자' | '□ 초기창업자' 처럼 선택 그룹이 칸으로 나뉘면 같은 행의 ■ 로 선택된 것이다(마포 실측 오탐)."""
    split = [["구분", "■ 예비창업자", "□초기창업자"]]
    assert inspect_fill(_hwpx(tmp_path / "split.hwpx", split)).findings == []
    none_selected = [["구분", "□ 예비창업자", "□초기창업자"]]
    assert [f.kind for f in inspect_fill(_hwpx(tmp_path / "none.hwpx", none_selected)).findings] == ["unchecked", "unchecked"]


# ── 해당 단계 (N/A 근거) ─────────────────────────────────────────────────────

def test_domain_na_carries_reason_and_evidence(tmp_path):
    path = _hwpx(tmp_path / "ok.hwpx", _PROFILE)
    report = _judge(path, Domain.BUSINESS_PLAN)
    na = [r for r in report.rules if r["status"] == "N/A"]
    assert na
    assert all(r["na_evidenced"] is True and r["na_reason"] and r["evidence"] and r["location"] for r in na)


def test_format_skip_is_counted_as_evidenced_na_not_pass(tmp_path):
    from docx import Document

    path = tmp_path / "bp.docx"
    doc = Document()
    doc.add_paragraph("사업계획서 본문")
    doc.save(str(path))
    report = _judge(path, Domain.BUSINESS_PLAN)
    skipped = [r for r in report.rules if r["basis"] == "skipped_format"]
    assert skipped and all(r["na_evidenced"] and r["na_reason"] and r["location"] for r in skipped)
    assert report.summary["na_evidenced"] >= len(skipped)
    total_pass = report.summary["passed_verified"] + report.summary["passed_process"]
    assert total_pass + len(skipped) == report.summary["pass"]


@pytest.mark.parametrize("guard", [
    {"status": "N/A", "reason": "양식에 해당 칸 없음"},          # 근거(위치) 없음
    {"status": "N/A", "reason": "", "evidence": "표1 3행"},     # 사유 없음
    {"status": "N/A"},
])
def test_unevidenced_na_is_fail(tmp_path, guard):
    path = _hwpx(tmp_path / "ok.hwpx", _PROFILE)
    report = enforce_lrules(Domain.CONSULTANT_APPLICATION, artifact_path=path, guards={"L053": guard})
    entry = _rule(report, "L053")
    assert entry["status"] == "FAIL"
    assert report.summary["na_unevidenced"] == 1
    assert not report.can_finalize


def test_evidenced_na_is_accepted(tmp_path):
    path = _hwpx(tmp_path / "ok.hwpx", _PROFILE)
    guard = {"status": "N/A", "reason": "이 양식엔 종업원수 표가 없음", "location": "section0 표 1~2 검색, '종업원' 라벨 0건"}
    report = enforce_lrules(Domain.CONSULTANT_APPLICATION, artifact_path=path, guards={"L053": guard})
    entry = _rule(report, "L053")
    assert entry["status"] == "N/A" and entry["na_evidenced"] is True
    assert entry["location"].startswith("section0")
    assert report.summary["na_unevidenced"] == 0


# ── 집계/호환 ────────────────────────────────────────────────────────────────

def test_summary_keeps_legacy_keys_and_adds_three_stage_counts(tmp_path):
    report = _judge(_hwpx(tmp_path / "ok.hwpx", _PROFILE, _STAFF_FILLED, _CHOICE_FILLED))
    for key in ("total", "pass", "na", "fail", "review_required", "unverifiable", "user_override"):
        assert key in report.summary
    for key in ("applicable", "fill_required", "filled", "passed_verified", "passed_process",
                "na_evidenced", "na_unevidenced"):
        assert key in report.summary
    text = report.summary_text()
    assert "해당" in text and "채움" in text and "통과" in text and "N/A" in text
    assert report.as_dict()["summary_text"] == text
    for rule in report.rules:  # 새 필드가 모든 규칙에 있고 기존 필드도 유지
        for key in ("applicable", "filled", "passed", "na_reason", "location", "evidence", "status"):
            assert key in rule


def test_judgment_rules_still_block_final_even_when_filled(tmp_path):
    report = _judge(_hwpx(tmp_path / "ok.hwpx", _PROFILE, _STAFF_FILLED, _CHOICE_FILLED))
    assert report.summary["review_required"] > 0 and not report.can_finalize


def test_fill_inspection_failure_is_unverifiable_not_pass(tmp_path):
    broken = tmp_path / "broken.hwpx"
    broken.write_bytes(b"not a zip")
    report = enforce_lrules(
        Domain.CONSULTANT_APPLICATION, artifact_path=broken,
        guards={"L053": {"passed": True, "evidence": "x"}},
    )
    assert _rule(report, "L053")["status"] == "UNVERIFIABLE"


# ── form_diff □→■ 오탐 ───────────────────────────────────────────────────────

def test_form_diff_checkbox_symbol_change_is_not_form_damage(tmp_path):
    src = _hwpx(tmp_path / "src.hwpx", [["사업자 형태", "□ 개인 □ 법인"]], _PROFILE[:1])
    dst = _hwpx(tmp_path / "dst.hwpx", [["사업자 형태", "■ 개인 □ 법인"]], _PROFILE[:1])
    rep = compare_hwpx_forms(src, dst)
    assert rep.form_intact is True
    assert rep.form_phrase_edits == 0 and rep.check_marks == 1 and rep.value_fills >= 1
    assert any("체크박스 기호 변경 1건" in n for n in rep.notes)


def test_form_diff_still_flags_real_label_edit_alongside_check(tmp_path):
    src = _hwpx(tmp_path / "src.hwpx", [["사업자 형태", "□ 개인 □ 법인"]])
    dst = _hwpx(tmp_path / "dst.hwpx", [["사업자 구분", "■ 개인 □ 법인"]])
    rep = compare_hwpx_forms(src, dst)
    assert rep.form_intact is False and rep.form_phrase_edits == 1 and rep.check_marks == 1


def test_form_diff_check_symbol_with_text_change_is_still_edit(tmp_path):
    src = _hwpx(tmp_path / "src.hwpx", [["구분", "□ 개인"]])
    dst = _hwpx(tmp_path / "dst.hwpx", [["구분", "■ 법인"]])
    assert compare_hwpx_forms(src, dst).form_phrase_edits == 1
