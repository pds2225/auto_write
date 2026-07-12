"""learning_report 리포트 생성 테스트 — 필수 섹션 존재, 원본 same-path 거부, 빈 결함 '없음' 표기."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_write.services.learning_report import build_learning_report, write_learning_report


def _run_record(final_file: str = "제출본.docx") -> dict:
    return {
        "run_id": "20260712_120000_ab12",
        "project_id": "p1",
        "program_name": "테스트 공고",
        "template_type": "docx",
        "final_file": final_file,
        "scores": {
            "eval_score": None, "eval_max": None, "quality_score": 95.0,
            "acceptance_fail": 2, "acceptance_warn": 1,
        },
        "verdict": "제출불가",
        "needs_input": ["대표자명 옆 칸"],
        "created_at": "2026-07-12T12:00:00+09:00",
    }


def test_build_report_contains_required_sections() -> None:
    md = build_learning_report(_run_record(), [], [], [])
    for heading in (
        "## 실행 요약", "## 평가 결과", "## 결함 분류",
        "## 자동 수정 대상 (auto_fix)", "## 사람 입력 필요 (human_input)",
        "## 프롬프트 규칙 후보 (prompt_rule)", "## 양식 매핑 후보 (field_mapping)",
        "## 코드 개선 후보 (code_improvement)", "## 다음 실행 반영 규칙",
    ):
        assert heading in md, f"필수 섹션 누락: {heading}"


def test_build_report_shows_none_marker_for_empty_defects() -> None:
    md = build_learning_report(_run_record(), [], [], [])
    assert "없음" in md


def test_build_report_lists_classified_defects() -> None:
    classified = [{
        "check_id": "unresolved_markers", "label": "[확인필요] 마커", "severity": "fail",
        "defects": 2, "samples": ["샘플"], "category": "human_input",
        "next_action": "실제 값을 입력하세요", "command": "",
    }]
    md = build_learning_report(_run_record(), classified, [], [])
    assert "unresolved_markers" in md
    assert "human_input" in md


def test_write_learning_report_creates_file(tmp_path: Path) -> None:
    record = _run_record(final_file=str(tmp_path / "제출본.docx"))
    out = write_learning_report(tmp_path / "out", record, [])
    assert out.exists()
    assert out.name == "learning_report.md"
    assert record["run_id"] in out.read_text(encoding="utf-8")


def test_write_learning_report_refuses_same_path_as_original(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    original = out_dir / "learning_report.md"
    record = _run_record(final_file=str(original))
    with pytest.raises(ValueError):
        write_learning_report(out_dir, record, [])
