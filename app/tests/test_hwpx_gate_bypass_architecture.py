"""공통 HWPX integrity gate 배선 자체를 지키는 회귀 검사."""

from __future__ import annotations

from pathlib import Path


APP = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (APP / relative).read_text(encoding="utf-8")


def test_final_hwpx_submit_entrypoints_use_common_gate():
    """최종 제출 경로가 acceptance-only 또는 직접 fill로 우회하지 않는지 확인한다."""
    service = _source("auto_write/services/hwpx_submit.py")
    cli = _source("hwpx_submit.py")
    cross_form = _source("cross_form_hwp_pipeline.py")

    assert "from .hwpx_integrity_gate import run_hwpx_integrity_gate" in service
    assert "gate = run_hwpx_integrity_gate(" in service
    assert "submit_hwpx" in cli
    assert "run_hwpx_integrity_gate" in cross_form
    assert 'result["integrity_gate"] = gate.as_dict()' in cross_form
    assert 'result["output_status"] = "PASS"' in cross_form


def test_gate_bypass_is_fail_closed():
    service = _source("auto_write/services/hwpx_submit.py")

    assert "if not acceptance_gate:" in service
    assert "APPROVAL_REQUIRED" in service
    assert "_mark_draft(report, out, src)" in service
    assert "report.ok = False" in service


def test_cross_form_does_not_create_submit_copy_without_gate_pass():
    source = _source("cross_form_hwp_pipeline.py")

    gate_check = 'Path(hwpx_src).is_file() and result.get("output_status") == "PASS"'
    blocked_marker = 'result["submit_blocked"] = {'
    assert gate_check in source
    assert blocked_marker in source
