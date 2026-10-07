"""출처목록: EvidenceSource·PDF 근거만, 날조 금지, DRAFT 게이트."""

from __future__ import annotations

from pathlib import Path

import fitz

from auto_write.image_automation.citation_report import (
    build_citations,
    is_submission_ready,
    normalize_url,
    requires_draft,
    write_citation_reports,
)
from auto_write.image_automation.models import CitationStatus
from auto_write.models import EvidenceSource


def _pdf_with_link(path: Path, url: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "ref")
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


def test_normalize_url():
    assert normalize_url("HTTPS://Example.COM/Path/") == "https://example.com/Path"


def test_verified_from_evidence_and_pdf(tmp_path: Path):
    url = "https://example.com/report"
    pdf = _pdf_with_link(tmp_path / "a.pdf", url)
    from auto_write.image_automation.citation_report import extract_pdf_hyperlinks

    urls = extract_pdf_hyperlinks(pdf)
    ev = [
        EvidenceSource(
            topic="market",
            title="시장조사 보고서",
            url=url,
            organization="통계청",
            summary="2024년 조사",
        )
    ]
    citations = build_citations(ev, pdf_urls=urls)
    citations[0].used_on = "slide:1"
    assert citations[0].status == CitationStatus.VERIFIED
    assert citations[0].year == "2024"
    assert is_submission_ready(citations)
    assert not requires_draft(citations)


def test_missing_url_is_draft():
    ev = [
        EvidenceSource(
            topic="x",
            title="자료",
            url="",
            organization="기관",
            summary="2023",
        )
    ]
    citations = build_citations(ev, pdf_urls=[])
    assert citations[0].status == CitationStatus.MISSING_URL
    assert requires_draft(citations)


def test_notebooklm_invented_url_mismatch():
    ev = [
        EvidenceSource(
            topic="x",
            title="자료",
            url="https://real.example/a",
            organization="기관",
            summary="2022년",
        )
    ]
    citations = build_citations(
        ev,
        pdf_urls=["https://real.example/a"],
        notebooklm_urls=["https://fake.example/invented"],
    )
    statuses = {c.status for c in citations}
    assert CitationStatus.MISMATCH in statuses
    assert requires_draft(citations)


def test_checked_at_not_used_as_year():
    ev = [
        EvidenceSource(
            topic="x",
            title="자료",
            url="https://example.com/a",
            organization="기관",
            summary="연도 없음",
            checked_at="2026-07-24T00:00:00Z",
        )
    ]
    citations = build_citations(ev, pdf_urls=["https://example.com/a"])
    assert citations[0].year == ""
    assert citations[0].status == CitationStatus.MISSING_YEAR


def test_write_sources_trio(tmp_path: Path):
    ev = [
        EvidenceSource(
            topic="x",
            title="자료A",
            url="https://example.com/a",
            organization="기관A",
            summary="2021 자료",
        )
    ]
    citations = build_citations(ev, pdf_urls=["https://example.com/a"])
    citations[0].used_on = "slide:1"
    paths = write_citation_reports(citations, tmp_path)
    assert paths["json"].is_file()
    assert paths["md"].is_file()
    assert paths["csv"].is_file()
    md = paths["md"].read_text(encoding="utf-8")
    assert "자료명" in md
    assert "기관명" in md
    assert "URL" in md
