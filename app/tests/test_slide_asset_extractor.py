"""슬라이드 분리: PDF → PNG."""

from __future__ import annotations

from pathlib import Path

import fitz

from auto_write.image_automation.slide_asset_extractor import extract_pdf_to_pngs, extract_slides


def _make_pdf(path: Path, pages: int = 3) -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"page-{i + 1}")
    doc.save(path)
    doc.close()
    return path


def test_pdf_page_count_matches_png(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "in.pdf", pages=10)
    out = tmp_path / "slides"
    result = extract_pdf_to_pngs(pdf, out, dpi=72)
    assert result.page_count == 10
    assert len(result.assets) == 10
    for i, asset in enumerate(result.assets, start=1):
        assert asset.slide_index == i
        assert asset.path_rel == f"slide-{i:03d}.png"
        assert (out / asset.path_rel).is_file()
        assert asset.sha256


def test_same_input_reuses_outputs(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "in.pdf", pages=2)
    out = tmp_path / "slides"
    first = extract_pdf_to_pngs(pdf, out, dpi=72)
    second = extract_pdf_to_pngs(pdf, out, dpi=72)
    assert first.reused is False
    assert second.reused is True
    assert [a.sha256 for a in first.assets] == [a.sha256 for a in second.assets]


def test_extract_slides_pdf(tmp_path: Path):
    pdf = _make_pdf(tmp_path / "in.pdf", pages=2)
    result = extract_slides(pdf, tmp_path / "out", dpi=72)
    assert result.page_count == 2
