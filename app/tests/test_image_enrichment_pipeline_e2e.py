"""M1 파이프라인: 외부 업로드 차단 스모크 + 슬라이드/출처."""

from __future__ import annotations

from pathlib import Path

import fitz

from auto_write.image_automation.m1_pipeline import run_m1
from auto_write.image_automation.notebooklm_browser import BrowserSessionStub, NotebookLMBrowser, SourceItem
from auto_write.image_automation.notebooklm_state import EXPECTED_SLIDE_DESCRIPTION
from auto_write.models import EvidenceSource


def _pdf(path: Path, pages: int = 2, url: str | None = None) -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"p{i+1}")
        if url and i == 0:
            page.insert_link(
                {
                    "kind": fitz.LINK_URI,
                    "from": fitz.Rect(70, 60, 200, 90),
                    "uri": url,
                }
            )
    doc.save(path)
    doc.close()
    return path


def test_m1_blocks_upload_without_flag(tmp_path: Path):
    pdf = _pdf(tmp_path / "in.pdf")
    result = run_m1(
        pdf,
        results_root=tmp_path / "runs",
        mode="notebooklm",
        allow_external_upload=False,
        cwd=Path("D:/auto_write-wt-m1-notebooklm"),
        evidence=[],
    )
    assert result.draft is True
    assert result.report["notebooklm"] == "external_upload_blocked"
    assert result.report["slides"]["page_count"] == 2
    assert (result.run_dir / "slides" / "slide-001.png").is_file()
    assert (result.run_dir / "citations" / "sources.md").is_file()


def test_m1_stub_with_allow_and_citations(tmp_path: Path):
    url = "https://example.com/doc"
    pdf = _pdf(tmp_path / "in.pdf", pages=3, url=url)
    dl = _pdf(tmp_path / "notebooklm_out.pdf", pages=3)
    session = BrowserSessionStub(
        notebooks=["auto_write"],
        sources=[],
        visible_labels={"슬라이드 자료", "발표자 슬라이드", "짧게", "생성"},
        notebook_url_id="nb-1",
        downloaded=dl,
    )
    browser = NotebookLMBrowser(
        allow_external_upload=True,
        cwd=Path("D:/auto_write-wt-m1-notebooklm"),
        session=session,
    )
    ev = [
        EvidenceSource(
            topic="t",
            title="공식통계",
            url=url,
            organization="통계청",
            summary="2024년 발표",
        )
    ]
    result = run_m1(
        pdf,
        results_root=tmp_path / "runs",
        mode="notebooklm",
        allow_external_upload=True,
        cwd=Path("D:/auto_write-wt-m1-notebooklm"),
        evidence=ev,
        browser=browser,
        slides_input=dl,
    )
    assert result.report["notebooklm"]["code"] == "done"
    assert result.report["notebooklm"]["generate_clicks"] == 1
    assert result.report["notebooklm"]["file_chooser_calls"] == 1
    assert result.report["slides"]["page_count"] == 3
    assert session.description == EXPECTED_SLIDE_DESCRIPTION
    assert result.draft is False
