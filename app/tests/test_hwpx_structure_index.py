# -*- coding: utf-8 -*-
"""Coordinate index: section, table, cell, paragraph, run, raw text.

This is not a write permission. Caption tables must be counted.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree

from core.docx.services.hwpx_analysis_adapter import _label_evidence, _table_cells, index_hwpx_structure

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_REAL = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "(별첨1) 2024년도 창업중심대학 예비창업자 사업계획서 양식.hwpx"
)


def _hwpx(path: Path, sections: list[tuple[str, str]], spine: list[str] | None) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        for name, xml in sections:
            archive.writestr(name, xml.encode("utf-8"))
        if spine is not None:
            items = []
            refs = []
            for index, href in enumerate(spine):
                items.append(f'<opf:item id="section{index}" href="{href}" media-type="application/xml"/>')
                refs.append(f'<opf:itemref idref="section{index}"/>')
            hpf = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<opf:package xmlns:opf="http://www.idpf.org/2007/opf/">'
                f"<opf:manifest>{''.join(items)}</opf:manifest>"
                f"<opf:spine>{''.join(refs)}</opf:spine>"
                "</opf:package>"
            )
            archive.writestr("Contents/content.hpf", hpf.encode("utf-8"))


def _sec(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _independent_paragraphs(path: Path, member: str) -> list[str]:
    """Re-read hp:p raw text in XML order, without the indexer."""
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read(member))

    def local(tag: object) -> str:
        text = str(tag or "")
        return text.rsplit("}", 1)[-1] if "}" in text else text

    def raw_t(node) -> str:
        parts = [node.text or ""]
        for child in node:
            if child.tail:
                parts.append(child.tail)
        return "".join(parts)

    paragraphs = []
    for element in root.iter():
        if local(element.tag) != "p":
            continue
        chunks = []
        for child in element:
            if local(child.tag) != "run":
                continue
            for sub in child:
                if local(sub.tag) == "t":
                    chunks.append(raw_t(sub))
        paragraphs.append("".join(chunks))
    return paragraphs


def test_caption_table_is_indexed_and_text_roundtrips(tmp_path: Path) -> None:
    src = tmp_path / "caption.hwpx"
    body = """
    <hp:p><hp:run><hp:t>outside</hp:t></hp:run></hp:p>
    <hp:p>
      <hp:run>
        <hp:tbl>
          <hp:caption>
            <hp:subList>
              <hp:p><hp:run>
                <hp:tbl>
                  <hp:tr><hp:tc>
                    <hp:subList><hp:p><hp:run><hp:t>CAP</hp:t></hp:run></hp:p></hp:subList>
                    <hp:cellAddr rowAddr="0" colAddr="0"/>
                    <hp:cellSpan rowSpan="1" colSpan="1"/>
                  </hp:tc></hp:tr>
                </hp:tbl>
              </hp:run></hp:p>
            </hp:subList>
          </hp:caption>
          <hp:tr><hp:tc>
            <hp:subList>
              <hp:p><hp:run><hp:t>LABEL</hp:t></hp:run></hp:p>
              <hp:p><hp:run><hp:t></hp:t></hp:run><hp:run><hp:t>  가</hp:t></hp:run></hp:p>
            </hp:subList>
            <hp:cellAddr rowAddr="0" colAddr="0"/>
            <hp:cellSpan rowSpan="1" colSpan="1"/>
          </hp:tc></hp:tr>
        </hp:tbl>
      </hp:run>
    </hp:p>
    """
    _hwpx(src, [("Contents/section0.xml", _sec(body))], ["Contents/section0.xml"])
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    assert src.read_bytes() == before
    assert index.analysis_status == "COMPLETE"
    assert index.table_count == 2
    assert index.tables[0].story_scope == "body"
    assert index.tables[1].story_scope == "caption"
    assert index.tables[1].parent_table_index == 0
    assert index.tables[1].table_path == (0,)
    assert index.tables[1].table_index_in_section == 1
    cell = index.tables[0].cells[0]
    assert (cell.row, cell.col, cell.physical_tr_index, cell.physical_tc_index) == (0, 0, 0, 0)
    texts = [item.raw_text for item in index.sections[0].paragraphs]
    assert "CAP" in texts
    assert "LABEL" in texts
    assert "  가" in texts
    whitespace = next(item for item in index.sections[0].paragraphs if item.raw_text == "  가")
    assert whitespace.runs[1].raw_text == "  가"
    assert _independent_paragraphs(src, "Contents/section0.xml") == [
        item.raw_text for item in index.sections[0].paragraphs
    ]


def test_missing_cell_address_stays_null_and_overlap_is_not_repaired(tmp_path: Path) -> None:
    src = tmp_path / "grid.hwpx"
    body = """
    <hp:p><hp:run>
      <hp:tbl>
        <hp:tr>
          <hp:tc>
            <hp:subList><hp:p><hp:run><hp:t>A</hp:t></hp:run></hp:p></hp:subList>
          </hp:tc>
          <hp:tc>
            <hp:subList><hp:p><hp:run><hp:t>B</hp:t></hp:run></hp:p></hp:subList>
            <hp:cellAddr rowAddr="0" colAddr="0"/>
            <hp:cellSpan rowSpan="1" colSpan="1"/>
          </hp:tc>
          <hp:tc>
            <hp:subList><hp:p><hp:run><hp:t>C</hp:t></hp:run></hp:p></hp:subList>
            <hp:cellAddr rowAddr="0" colAddr="0"/>
            <hp:cellSpan rowSpan="1" colSpan="1"/>
          </hp:tc>
        </hp:tr>
      </hp:tbl>
    </hp:run></hp:p>
    """
    _hwpx(src, [("Contents/section0.xml", _sec(body))], ["Contents/section0.xml"])
    index = index_hwpx_structure(src)
    cells = index.tables[0].cells
    assert cells[0].row is None and cells[0].col is None
    assert cells[0].address_status == "MISSING"
    assert cells[1].row == 0 and cells[2].row == 0
    assert index.tables[0].addresses_overlap is True
    assert index.analysis_status == "PARTIAL"
    assert any(item.startswith("COORDINATE_OVERLAP") for item in index.errors)


def test_section_order_follows_spine_not_filename_sort(tmp_path: Path) -> None:
    src = tmp_path / "order.hwpx"
    _hwpx(
        src,
        [
            ("Contents/section0.xml", _sec("<hp:p><hp:run><hp:t>ZERO</hp:t></hp:run></hp:p>")),
            ("Contents/section1.xml", _sec("<hp:p><hp:run><hp:t>ONE</hp:t></hp:run></hp:p>")),
        ],
        ["Contents/section1.xml", "Contents/section0.xml"],
    )
    index = index_hwpx_structure(src)
    assert index.section_order == ("Contents/section1.xml", "Contents/section0.xml")
    assert index.sections[0].paragraphs[0].raw_text == "ONE"
    assert index.sections[1].paragraphs[0].raw_text == "ZERO"
    assert index.section_order_confirmed is True


def test_legacy_table_cells_keep_missing_addresses_null() -> None:
    table = etree.fromstring(
        """
        <hp:tbl xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
          <hp:tr>
            <hp:tc><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList></hp:tc>
            <hp:tc>
              <hp:cellAddr rowAddr="0" colAddr="1"/>
              <hp:cellSpan rowSpan="1" colSpan="1"/>
              <hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
            </hp:tc>
          </hp:tr>
          <hp:tr>
            <hp:tc>
              <hp:cellAddr rowAddr="1" colAddr="3"/>
              <hp:cellSpan rowSpan="0" colSpan="1"/>
              <hp:subList><hp:p><hp:run><hp:t>값</hp:t></hp:run></hp:p></hp:subList>
            </hp:tc>
          </hp:tr>
        </hp:tbl>
        """
    )
    cells = _table_cells(table)
    assert cells[0]["row_index"] == 0 and cells[0]["row_cell_index"] == 0
    assert cells[0]["row"] is None and cells[0]["col"] is None
    assert cells[0]["row_span"] is None and cells[0]["col_span"] is None
    assert cells[0]["has_address"] is False
    assert cells[1]["row"] == 0 and cells[1]["col"] == 1
    assert cells[2]["row"] == 1 and cells[2]["col"] == 3
    assert cells[2]["row_span"] is None and cells[2]["col_span"] is None
    assert all(cell["grid_valid"] is False for cell in cells)
    assert _label_evidence(cells[1], cells, table, {}) == ("", None)

    placed = etree.fromstring(
        """
        <hp:tbl xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
          <hp:tr>
            <hp:tc>
              <hp:cellAddr rowAddr="0" colAddr="0"/>
              <hp:cellSpan rowSpan="1" colSpan="1"/>
              <hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>
            </hp:tc>
            <hp:tc>
              <hp:cellAddr rowAddr="0" colAddr="1"/>
              <hp:cellSpan rowSpan="1" colSpan="1"/>
              <hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
            </hp:tc>
          </hp:tr>
        </hp:tbl>
        """
    )
    ready = _table_cells(placed)
    assert all(cell["grid_valid"] is True for cell in ready)
    assert [cell["col"] for cell in ready] == [0, 1]
    label, evidence = _label_evidence(ready[1], ready, placed, {})
    assert label == "기업명"
    assert evidence["kind"] == "left_cell"


def test_real_form_counts_caption_table() -> None:
    if not _REAL.is_file():
        pytest.skip("sample form is not in this workspace")
    index = index_hwpx_structure(_REAL)
    assert index.analysis_status == "COMPLETE"
    assert index.table_count == 50
    assert sum(1 for table in index.tables if table.story_scope == "caption") == 1
    assert _independent_paragraphs(_REAL, "Contents/section0.xml") == [
        item.raw_text for item in index.sections[0].paragraphs
    ]
    assert index.source_sha256 == again_hash(_REAL)


def again_hash(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_negative_cell_address_is_not_complete(tmp_path: Path) -> None:
    def body(row: str, col: str) -> str:
        return _sec(
            "<hp:p><hp:run><hp:tbl><hp:tr><hp:tc>"
            "<hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>"
            f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
            '<hp:cellSpan rowSpan="1" colSpan="1"/>'
            "</hp:tc></hp:tr></hp:tbl></hp:run></hp:p>"
        )
    from core.docx.services.hwpx_protected_regions import find_t02_auto_targets
    for row, col in (("-1", "0"), ("0", "-1")):
        src = tmp_path / f"bad-{row}-{col}.hwpx"
        _hwpx(src, [("Contents/section0.xml", body(row, col))], ["Contents/section0.xml"])
        index = index_hwpx_structure(src)
        assert index.analysis_status != "COMPLETE"
        assert any(item.startswith("INVALID_COORDINATE") for item in index.errors)
        assert index.tables[0].cells[0].address_status == "INVALID"
        assert index.tables[0].cells[0].row is None
        assert find_t02_auto_targets(index) == ()


def test_header_and_footer_tables_are_not_body_fields(tmp_path: Path) -> None:
    def region(tag: str, label: str) -> str:
        return (
            f"<hp:p><hp:run><hp:ctrl><hp:{tag}><hp:subList><hp:p><hp:run><hp:tbl><hp:tr>"
            "<hp:tc><hp:subList><hp:p><hp:run><hp:t>" + label + "</hp:t></hp:run></hp:p></hp:subList>"
            '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
            "<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>"
            '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
            f"</hp:tr></hp:tbl></hp:run></hp:p></hp:subList></hp:{tag}></hp:ctrl></hp:run></hp:p>"
        )
    src = tmp_path / "stories.hwpx"
    _hwpx(src, [("Contents/section0.xml", _sec(region("header", "기업명") + region("footer", "주소")))], ["Contents/section0.xml"])
    index = index_hwpx_structure(src)
    assert index.analysis_status == "COMPLETE"
    assert [table.story_scope for table in index.tables] == ["header", "footer"]
    from core.docx.services.hwpx_protected_regions import assess_fields, find_t02_auto_targets
    assert find_t02_auto_targets(index) == ()
    scopes = {item.story_scope for item in assess_fields(index) if item.table_index is not None}
    assert "header" in scopes and "footer" in scopes and "body" not in scopes
