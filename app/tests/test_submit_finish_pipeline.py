"""제출 마감 파이프라인 통합(가짜 데이터·가짜 변환기). 외부 AI·실제 한글 COM 호출 없음."""
from __future__ import annotations

import json
from pathlib import Path

import fitz

from auto_write.services.submit_finish.pipeline import SubmitFinishInputs, run_submit_finish
from auto_write.services.submit_finish.status import Status
from test_submit_finish_seal_checkbox import _p, _tbl, _write_hwpx


def _fake_converter(hwpx: Path, pdf: Path) -> None:
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    for i in range(5):
        pg.insert_text((60, 100 + 20 * i), f"참가신청서 본문 {i} 가짜 데이터", fontname="korea", fontsize=11)
    doc.save(pdf)


def _attachment(path: Path) -> Path:
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.insert_text((60, 100), "주민등록초본 가짜 데이터", fontname="korea", fontsize=11)
    doc.save(path)
    return path


def _form(tmp_path: Path) -> Path:
    body = (_tbl([[[_p("사업자 구분")], [_p("□ 개인 □ 법인")]]])
            + _p("1. 개인정보 수집·이용 동의") + _p("□ 동의함 □ 동의하지 않음"))
    src = tmp_path / "filled.hwpx"
    _write_hwpx(src, body)
    return src


def test_pipeline_end_to_end_synthetic(tmp_path: Path) -> None:
    src = _form(tmp_path)
    att = _attachment(tmp_path / "초본.pdf")
    inp = SubmitFinishInputs(
        filled_hwpx=src, out_dir=tmp_path / "out", doc_name="참가신청서", company="가짜주식회사", rep="홍길동",
        baseline_form=src,
        checkbox_decisions={"사업자 구분": {"value": "법인", "source": "company_master", "single": True}},
        attachments=[att], redact_attachments=False,   # 가림 미확인 → 외부 AI 전송 차단 경로 검증
        converter=_fake_converter, expected_page_order=["참가신청서", "주민등록초본"],
    )
    before = src.read_bytes()
    res = run_submit_finish(inp)
    assert src.read_bytes() == before                      # 입력 불변
    assert Path(res.artifacts["final_hwpx"]).is_file()
    assert res.report_json and res.report_json.is_file() and res.report_md.is_file()
    json.loads(res.report_json.read_text(encoding="utf-8"))
    merged = Path(res.artifacts["merged_pdf"])
    assert merged.is_file() and merged.name.endswith(".pdf")
    assert fitz.open(merged).page_count == 2
    codes = [f.code for f in res.findings]
    assert codes.count("PDF_LAYOUT") == 1                  # 검사가 중복 실행되지 않는다
    assert "PDF_ORDER_WRONG" not in codes and "PDF_ORDER_MISSING" not in codes


def test_pipeline_failed_conversion_makes_no_merged_pdf(tmp_path: Path) -> None:
    def bad(hwpx, pdf):
        raise RuntimeError("변환 실패(가짜)")

    inp = SubmitFinishInputs(filled_hwpx=_form(tmp_path), out_dir=tmp_path / "out2", doc_name="참가신청서",
                             company="가짜", rep="홍길동", converter=bad, apply_submission_cleanup=False)
    res = run_submit_finish(inp)
    assert "merged_pdf" not in res.artifacts
    assert any(f.status is Status.FAIL for f in res.findings)
    assert res.report_json.is_file()
