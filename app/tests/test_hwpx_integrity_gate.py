"""공통 HWPX integrity gate의 실행상태·severity·실제 제출배선 검증."""

from __future__ import annotations

import zipfile
from pathlib import Path

from auto_write.services.hwpx_integrity_gate import (
    HARD_FAIL,
    PASS,
    REVIEW_REQUIRED,
    ERROR,
    EXECUTED,
    TIMEOUT,
    UNAVAILABLE,
    run_hwpx_integrity_gate,
)
from auto_write.services.hwpx_submit import submit_hwpx

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _row(row: int, label: str, value: str) -> str:
    return (
        f'<hp:tr><hp:tc><hp:cellAddr colAddr="0" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>{label}</hp:t>'
        '</hp:run></hp:p></hp:subList></hp:tc>'
        f'<hp:tc><hp:cellAddr colAddr="1" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>{value}</hp:t>'
        '</hp:run></hp:p></hp:subList></hp:tc></hp:tr>'
    )


def _make_hwpx(path: Path, *, broken_grid: bool = False) -> Path:
    rows = [_row(0, "상호", ""), _row(1, "대표자", "")]
    if broken_grid:
        rows.append(_row(1, "주소", ""))
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{HP}" xmlns:hs="{HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="{len(rows)}" colCnt="2">'
        f'{"".join(rows)}</hp:tbl></hp:run></hp:p></hs:sec>'
    ).encode("utf-8")
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{HH}"><hh:charPr id="0" textColor="#000000"/>'
        '</hh:head>'
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, "application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section)
    return path


def _ok_acceptance(*_args, **_kwargs):
    return {"ok": True, "fail_defects": 0}


def test_gate_aggregates_clean_structural_validators(tmp_path: Path):
    source = _make_hwpx(tmp_path / "clean.hwpx")
    report = run_hwpx_integrity_gate(
        str(source), acceptance_validator=_ok_acceptance
    )
    assert report.final_status == PASS
    assert report.ok is True
    assert all(v.validator_status == EXECUTED for v in report.validators)


def test_gate_structural_failure_is_hard_fail(tmp_path: Path):
    source = _make_hwpx(tmp_path / "broken.hwpx", broken_grid=True)
    report = run_hwpx_integrity_gate(str(source), acceptance_validator=_ok_acceptance)
    assert report.final_status == HARD_FAIL
    semantic = next(v for v in report.validators if v.source_validator == "check_hwpx_semantics")
    assert semantic.validator_status == EXECUTED
    assert semantic.severity == HARD_FAIL
    assert semantic.evidence["report"]["broken_tables"]


def test_gate_execution_error_never_becomes_pass(tmp_path: Path):
    source = _make_hwpx(tmp_path / "error.hwpx")

    def boom(*_args, **_kwargs):
        raise RuntimeError("validator exploded")

    report = run_hwpx_integrity_gate(
        str(source), semantic_validator=boom, acceptance_validator=_ok_acceptance
    )
    result = report.validators[0]
    assert report.final_status == HARD_FAIL
    assert result.validator_status == ERROR
    assert result.evidence["failure_code"] == "CHECK_HWPX_SEMANTICS_ERROR"
    assert "validator exploded" in result.evidence["exception"]
    assert result.evidence["environment"]["python"]


def test_gate_unavailable_structural_validator_is_hard_fail(tmp_path: Path):
    source = _make_hwpx(tmp_path / "unavailable.hwpx")

    def missing(*_args, **_kwargs):
        raise ModuleNotFoundError("optional validator missing")

    report = run_hwpx_integrity_gate(
        str(source), semantic_validator=missing, acceptance_validator=_ok_acceptance
    )
    result = report.validators[0]
    assert report.final_status == HARD_FAIL
    assert result.validator_status == UNAVAILABLE
    assert result.severity == HARD_FAIL
    assert result.evidence["failure_code"] == "CHECK_HWPX_SEMANTICS_UNAVAILABLE"


def test_rendering_timeout_is_review_and_hard_fail_wins(tmp_path: Path):
    source = _make_hwpx(tmp_path / "render-timeout.hwpx")

    def timeout(_path):
        raise TimeoutError("renderer timeout")

    report = run_hwpx_integrity_gate(
        str(source),
        semantic_validator=lambda _path: {"ok": True},
        acceptance_validator=_ok_acceptance,
        render_validator=timeout,
    )
    assert report.final_status == REVIEW_REQUIRED
    rendering = next(v for v in report.validators if v.source_validator == "rendering_validator")
    assert rendering.validator_status == TIMEOUT
    assert rendering.severity == REVIEW_REQUIRED


def test_fixed_cell_overflow_is_review_until_real_render(tmp_path: Path):
    source = _make_hwpx(tmp_path / "fixed-cell-risk.hwpx")
    report = run_hwpx_integrity_gate(
        str(source),
        acceptance_validator=_ok_acceptance,
        fixed_cell_overflow=["주소=긴 텍스트"],
    )
    assert report.final_status == REVIEW_REQUIRED
    risk = next(v for v in report.validators if v.source_validator == "fixed_cell_height_guard")
    assert risk.validator_status == EXECUTED
    assert risk.evidence["render_confirmed"] is False


def test_submit_repairs_simple_broken_grid_before_gate(tmp_path: Path):
    source = _make_hwpx(tmp_path / "broken-input.hwpx", broken_grid=True)
    output = tmp_path / "result.hwpx"
    report = submit_hwpx(source, output, identity={"기업명": "테스트기업"})
    assert report.ok is True
    assert Path(report.final) == output
    assert report.integrity["final_status"] == PASS
    assert report.integrity["ok"] is True
