# -*- coding: utf-8 -*-
"""원본 HWPX 필수 구조 생존과 최종 렌더 증거 게이트 회귀."""

from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
import zipfile

from auto_write.services import hwpx_template_survival as survival
from auto_write.services.hwpx_integrity_gate import PASS, REVIEW_REQUIRED, run_hwpx_integrity_gate


HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"
HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _cell(col: int, row: int, text: str, *, col_span: int = 1) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="{col_span}" rowSpan="1"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f'<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
    )


def _table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<hp:tr>{_cell(0, row, label)}{_cell(1, row, value)}</hp:tr>"
        for row, (label, value) in enumerate(rows)
    )
    return f'<hp:tbl rowCnt="{len(rows)}" colCnt="2">{body}</hp:tbl>'


def _make_hwpx(path: Path, *, include_plan: bool = True, include_pledge: bool = True) -> Path:
    chunks = []
    if include_plan:
        chunks.append(
            '<hp:p><hp:run charPrIDRef="0"><hp:t>사업계획서</hp:t></hp:run></hp:p>'
            '<hp:p><hp:run charPrIDRef="0">'
            + _table([("아이디어명", ""), ("아이디어 제안배경", "")])
            + "</hp:run></hp:p>"
        )
    if include_pledge:
        chunks.append(
            '<hp:p><hp:run charPrIDRef="0"><hp:t>참가 서약서</hp:t></hp:run></hp:p>'
            '<hp:p><hp:run charPrIDRef="0">'
            + _table([("신청자명", ""), ("서명", "")])
            + "</hp:run></hp:p>"
        )
    chunks.append(
        '<hp:p><hp:run charPrIDRef="0"><hp:t>개인정보 수집·이용 및 제3자 제공 동의서</hp:t></hp:run></hp:p>'
        '<hp:p><hp:run charPrIDRef="0">'
        + _table([("신청자", ""), ("동의", "□ 동의함")])
        + "</hp:run></hp:p>"
    )
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{HP}" xmlns:hs="{HS}">'
        + "".join(chunks)
        + "</hs:sec>"
    ).encode("utf-8")
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{HH}"><hh:charPr id="0" textColor="#000000"/>'
        "</hh:head>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, "application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section)
    return path


def _ok(*_args, **_kwargs):
    return {"ok": True}


def test_template_survival_allows_text_fill_without_structure_loss(tmp_path: Path):
    baseline = _make_hwpx(tmp_path / "baseline.hwpx")
    candidate = tmp_path / "candidate.hwpx"
    candidate.write_bytes(baseline.read_bytes())
    with zipfile.ZipFile(candidate, "a") as z:
        section = z.read("Contents/section0.xml")
        section = section.replace(b"<hp:t></hp:t>", "작성내용".encode("utf-8"), 1)
        z.writestr("Contents/section0.xml", section)

    report = survival.compare_hwpx_template_survival(
        baseline, candidate, require_protected_anchors=False
    )
    assert report["ok"] is True
    assert report["structure_loss"] == []


def test_template_survival_fails_when_business_plan_table_disappears(tmp_path: Path):
    baseline = _make_hwpx(tmp_path / "baseline.hwpx")
    candidate = _make_hwpx(tmp_path / "candidate.hwpx", include_plan=False)

    report = survival.compare_hwpx_template_survival(
        baseline, candidate, require_protected_anchors=False
    )
    assert report["ok"] is False
    assert "STRUCTURAL_LOSS" in report["defect_codes"]
    assert any(item["metric"] == "tables" for item in report["structure_loss"])


def test_template_survival_fails_when_protected_heading_anchor_disappears(tmp_path: Path, monkeypatch):
    baseline = _make_hwpx(tmp_path / "baseline.hwpx")
    candidate = _make_hwpx(tmp_path / "candidate.hwpx")
    baseline_key = str(baseline.resolve())
    candidate_key = str(candidate.resolve())

    def _anchors(path: Path):
        key = str(Path(path).resolve())
        if key == baseline_key:
            return Counter({"사업계획서": 1, "참가 서약서": 1, "개인정보 수집": 1})
        if key == candidate_key:
            return Counter({"참가 서약서": 1, "개인정보 수집": 1})
        raise AssertionError(key)

    monkeypatch.setattr(survival, "_protected_anchors", _anchors)
    report = survival.compare_hwpx_template_survival(baseline, candidate)
    assert report["ok"] is False
    assert "PROTECTED_ANCHOR_LOSS" in report["defect_codes"]
    assert report["missing_anchors"][0]["text"] == "사업계획서"


def test_render_evidence_required_rejects_not_run(tmp_path: Path):
    candidate = _make_hwpx(tmp_path / "candidate.hwpx")

    def _not_run(_path: str):
        return {
            "ok": False,
            "severity": "PASS",
            "render_status": "NOT_RUN",
            "reopen_status": "NOT_RUN",
            "visual_review": "NOT_RUN",
            "disabled": True,
        }

    report = run_hwpx_integrity_gate(
        str(candidate),
        semantic_validator=_ok,
        acceptance_validator=_ok,
        render_validator=_not_run,
        require_render_evidence=True,
    )
    assert report.final_status == REVIEW_REQUIRED
    render = next(v for v in report.validators if v.source_validator == "rendering_validator")
    assert render.defect_code == "RENDER_NOT_RUN_REQUIRED"


def test_render_evidence_required_needs_visual_and_hash_chain(tmp_path: Path):
    candidate = _make_hwpx(tmp_path / "candidate.hwpx")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()

    def _rendered_but_not_reviewed(_path: str):
        return {
            "ok": False,
            "severity": "REVIEW_REQUIRED",
            "render_status": "PASS",
            "reopen_status": "PASS",
            "visual_review": "NOT_RUN",
            "candidate_sha256": digest,
            "render_source_sha256": digest,
        }

    report = run_hwpx_integrity_gate(
        str(candidate),
        semantic_validator=_ok,
        acceptance_validator=_ok,
        render_validator=_rendered_but_not_reviewed,
        require_render_evidence=True,
    )
    assert report.final_status == REVIEW_REQUIRED
    render = next(v for v in report.validators if v.source_validator == "rendering_validator")
    assert render.defect_code == "RENDER_EVIDENCE_INCOMPLETE"


def test_render_evidence_required_accepts_complete_evidence(tmp_path: Path):
    candidate = _make_hwpx(tmp_path / "candidate.hwpx")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()

    def _complete(_path: str):
        return {
            "ok": True,
            "severity": "PASS",
            "render_status": "PASS",
            "reopen_status": "PASS",
            "visual_review": "PASS",
            "candidate_sha256": digest,
            "render_source_sha256": digest,
        }

    report = run_hwpx_integrity_gate(
        str(candidate),
        semantic_validator=_ok,
        acceptance_validator=_ok,
        render_validator=_complete,
        require_render_evidence=True,
    )
    assert report.final_status == PASS
    assert report.ok is True
