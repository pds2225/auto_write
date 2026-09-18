"""R9 수용검사와 공통 HWPX final gate의 최종 상태 전달 검증."""

from __future__ import annotations

import zipfile
from pathlib import Path

from auto_write.services.hwpx_integrity_gate import HARD_FAIL, PASS
from auto_write.services.hwpx_submit import submit_hwpx

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _make_hwpx(path: Path, *, r9_invalid: bool = False) -> Path:
    """COM 없이 R9 유색 charPr 결함을 재현하는 최소 HWPX fixture."""
    color = "#FF0000" if r9_invalid else "#000000"
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{HH}"><hh:charPr id="0" textColor="{color}"/>'
        "</hh:head>"
    ).encode("utf-8")
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{HP}" xmlns:hs="{HS}">'
        '<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="1">'
        '<hp:tr><hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p>'
        '<hp:run charPrIDRef="0"><hp:t>상호</hp:t></hp:run>'
        "</hp:p></hp:subList></hp:tc></hp:tr></hp:tbl>"
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, "application/hwp+zip")
        archive.writestr("Contents/header.xml", header)
        archive.writestr("Contents/section0.xml", section)
    return path


def test_r9_failure_reaches_common_gate_and_blocks_final_output(tmp_path: Path):
    source = _make_hwpx(tmp_path / "r9-invalid.hwpx", r9_invalid=True)
    requested = tmp_path / "result.hwpx"

    report = submit_hwpx(
        source,
        requested,
        identity={"기업명": "테스트기업"},
        normalize_colors=False,
        submission_cleanup=False,
    )

    assert report.ok is False
    assert report.integrity["final_status"] == HARD_FAIL
    acceptance = next(
        item
        for item in report.integrity["validators"]
        if item["source_validator"] == "run_hwpx_acceptance"
    )
    assert acceptance["severity"] == HARD_FAIL
    assert report.acceptance["ok"] is False
    assert report.final_output_allowed is False
    assert report.submittable is False
    assert Path(report.final).name == "result_DRAFT.hwpx"
    assert Path(report.final).exists()
    assert not requested.exists()


def test_r9_pass_keeps_normal_final_output(tmp_path: Path):
    source = _make_hwpx(tmp_path / "r9-valid.hwpx")
    requested = tmp_path / "result.hwpx"

    report = submit_hwpx(source, requested, identity={"기업명": "테스트기업"})

    assert report.ok is True
    assert report.integrity["final_status"] == PASS
    assert report.final_output_allowed is True
    assert report.submittable is True
    assert Path(report.final) == requested
    assert requested.exists()
    assert report.acceptance["ok"] is True


def test_r9_invalid_document_cannot_bypass_common_gate(tmp_path: Path):
    source = _make_hwpx(tmp_path / "r9-invalid-bypass.hwpx", r9_invalid=True)
    requested = tmp_path / "result.hwpx"

    report = submit_hwpx(
        source,
        requested,
        identity={"기업명": "테스트기업"},
        acceptance_gate=False,
        normalize_colors=False,
        submission_cleanup=False,
    )

    assert report.ok is False
    assert report.integrity["final_status"] == HARD_FAIL
    assert report.final_output_allowed is False
    assert report.submittable is False
    assert Path(report.final).name == "result_DRAFT.hwpx"
    assert not requested.exists()
