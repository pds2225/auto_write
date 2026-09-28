# -*- coding: utf-8 -*-
"""XML scope diff: only an explicit text target may change."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from lxml import etree

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_xml_scope_diff import (
    XmlScopeTarget,
    compare_hwpx_xml_scope,
    iter_section_paragraphs,
    paragraph_raw_text,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_REAL = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "(서식09) 연구개발기관 대표의 참여의사 확인서_접수번호(기관명).hwpx"
)


def _section() -> str:
    cell = (
        "<hp:tc><hp:subList><hp:p><hp:run charPrIDRef=\"{style}\"><hp:t>{text}</hp:t></hp:run></hp:p></hp:subList>"
        "<hp:cellAddr rowAddr=\"{row}\" colAddr=\"{col}\"/>"
        "<hp:cellSpan rowSpan=\"1\" colSpan=\"1\"/></hp:tc>"
    )
    rows = (
        "<hp:tr>"
        + cell.format(style="1", text="기업명", row=0, col=0)
        + cell.format(style="1", text="", row=0, col=1)
        + "</hp:tr><hp:tr>"
        + cell.format(style="1", text="주소", row=1, col=0)
        + cell.format(style="1", text="", row=1, col=1)
        + "</hp:tr>"
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run charPrIDRef=\"0\"><hp:tbl>{rows}</hp:tbl></hp:run></hp:p>"
        "<hp:p><hp:run charPrIDRef=\"2\"><hp:t>※ 안내문입니다</hp:t></hp:run></hp:p>"
        "</hs:sec>"
    )


def _header() -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><hh:head xmlns:hh="{_HH}" page="1"/>'


def _write(path: Path, section: str, header: str | None = None) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", (header or _header()).encode("utf-8"))
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("BinData/keep.bin", b"UNTOUCHED")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_text(section: str, paragraph_index: int, text: str) -> str:
    root = etree.fromstring(section.encode("utf-8"))
    paragraph = list(iter_section_paragraphs(root))[paragraph_index]
    node = next(child for child in paragraph[0] if child.tag.endswith("t"))
    node.text = text
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")


def _set_attr(section: str, paragraph_index: int, attr: str, value: str, *, on_run: bool = False) -> str:
    root = etree.fromstring(section.encode("utf-8"))
    paragraph = list(iter_section_paragraphs(root))[paragraph_index]
    if on_run:
        paragraph[0].set(attr, value)
    else:
        parent = paragraph.getparent()
        while parent is not None and not str(parent.tag).endswith("tc"):
            parent = parent.getparent()
        addr = next(child for child in parent if str(child.tag).endswith("cellAddr"))
        addr.set(attr, value)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")


def _target(paragraph: int, text_node: int | None = 0) -> XmlScopeTarget:
    return XmlScopeTarget("Contents/section0.xml", paragraph, 0, text_node)


def _compare(before: Path, after: Path, targets: list[XmlScopeTarget], sha: str):
    original = before.read_bytes()
    report = compare_hwpx_xml_scope(before, after, targets, expected_sha256=sha)
    assert before.read_bytes() == original
    assert report.source_unchanged is True
    assert report.source_sha256 == sha
    return report


def test_exact_target_text_change_passes(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    dst = tmp_path / "after.hwpx"
    _write(dst, _set_text(_section(), 2, "도보네비"))
    report = _compare(src, dst, [_target(2)], sha)
    assert report.ok is True and report.verdict == "PASS"
    assert report.unexpected_count == 0
    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.disposition == "allowed"
    assert change.member == "Contents/section0.xml"
    assert change.before == ""
    assert change.after == "도보네비"
    assert change.related_target is not None


def test_label_change_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    edited = _set_text(_set_text(_section(), 2, "도보네비"), 1, "상호")
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2)], sha)
    assert report.ok is False and report.verdict == "OUT_OF_SCOPE_XML_CHANGE"
    unexpected = [item for item in report.changes if item.disposition == "unexpected"]
    assert unexpected
    assert any(item.before == "기업명" and item.after == "상호" for item in unexpected)


def test_guidance_change_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    edited = _set_text(_set_text(_section(), 2, "도보네비"), 5, "※ 바꾼 안내")
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2)], sha)
    assert report.verdict == "OUT_OF_SCOPE_XML_CHANGE"
    assert any("안내문" in item.before and "바꾼 안내" in item.after for item in report.changes)


def test_other_cell_change_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    edited = _set_text(_set_text(_section(), 2, "도보네비"), 4, "서울")
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2)], sha)
    assert report.verdict == "OUT_OF_SCOPE_XML_CHANGE"
    assert any(item.after == "서울" and item.disposition == "unexpected" for item in report.changes)
    assert any(item.after == "도보네비" and item.disposition == "allowed" for item in report.changes)


def test_table_and_style_change_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    edited = _set_text(_section(), 2, "도보네비")
    edited = _set_attr(edited, 2, "rowAddr", "9")
    edited = _set_attr(edited, 5, "charPrIDRef", "99", on_run=True)
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2)], sha)
    assert report.verdict == "OUT_OF_SCOPE_XML_CHANGE"
    paths = " ".join(item.xml_path for item in report.changes if item.disposition == "unexpected")
    assert "rowAddr" in paths
    assert "charPrIDRef" in paths


def test_one_target_outside_its_range_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    edited = _set_text(_set_text(_section(), 2, "도보네비"), 4, "서울")
    edited = _set_text(edited, 3, "소재지")
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2), _target(4)], sha)
    assert report.verdict == "OUT_OF_SCOPE_XML_CHANGE"
    allowed = [item for item in report.changes if item.disposition == "allowed"]
    unexpected = [item for item in report.changes if item.disposition == "unexpected"]
    assert len(allowed) == 2
    assert any(item.before == "주소" and item.after == "소재지" for item in unexpected)


def test_header_change_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    sha = _write(src, _section())
    dst = tmp_path / "after.hwpx"
    _write(dst, _set_text(_section(), 2, "도보네비"), header=_header().replace('page="1"', 'page="2"'))
    report = _compare(src, dst, [_target(2)], sha)
    assert report.verdict == "OUT_OF_SCOPE_XML_CHANGE"
    assert any(item.member == "Contents/header.xml" and item.disposition == "unexpected" for item in report.changes)


def test_sha_mismatch_writes_nothing_and_fails(tmp_path: Path) -> None:
    src = tmp_path / "before.hwpx"
    _write(src, _section())
    dst = tmp_path / "after.hwpx"
    _write(dst, _set_text(_section(), 2, "도보네비"))
    report = compare_hwpx_xml_scope(src, dst, [_target(2)], expected_sha256="0" * 64)
    assert report.ok is False and report.verdict == "SHA_MISMATCH"
    assert report.sha_ok is False
    assert report.changes == []


def test_empty_run_insertion_is_allowed(tmp_path: Path) -> None:
    bare = _section().replace("<hp:t></hp:t>", "", 1)
    src = tmp_path / "before.hwpx"
    sha = _write(src, bare)
    root = etree.fromstring(bare.encode("utf-8"))
    paragraph = list(iter_section_paragraphs(root))[2]
    run = paragraph[0]
    created = etree.SubElement(run, f"{{{_HP}}}t")
    created.text = "도보네비"
    edited = etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2, None)], sha)
    assert report.ok is True and report.verdict == "PASS"
    assert report.changes[0].disposition == "allowed"
    assert report.changes[0].after == "도보네비"


def _inserted(mutate) -> tuple[str, str, str]:
    bare = _section().replace("<hp:t></hp:t>", "", 1)
    root = etree.fromstring(bare.encode("utf-8"))
    paragraph = list(iter_section_paragraphs(root))[2]
    run = paragraph[0]
    created = etree.SubElement(run, f"{{{_HP}}}t")
    created.text = "도보네비"
    mutate(created, run)
    edited = etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")
    return bare, edited, ""


def test_new_text_node_tail_sibling_and_attr_stay_visible(tmp_path: Path) -> None:
    def tail(created, _run) -> None:
        created.tail = "TAIL"

    def attr(created, _run) -> None:
        created.set("charPrIDRef", "9")

    def sibling(_created, run) -> None:
        run.set("charPrIDRef", "8")

    for mutate in (tail, attr, sibling):
        bare, edited, _unused = _inserted(mutate)
        src = tmp_path / "before.hwpx"
        sha = _write(src, bare)
        dst = tmp_path / "after.hwpx"
        _write(dst, edited)
        report = _compare(src, dst, [_target(2, None)], sha)
        assert report.ok is False and report.unexpected_count > 0


def test_wrong_namespace_text_node_is_unexpected(tmp_path: Path) -> None:
    bare = _section().replace("<hp:t></hp:t>", "", 1)
    root = etree.fromstring(bare.encode("utf-8"))
    paragraph = list(iter_section_paragraphs(root))[2]
    run = paragraph[0]
    created = etree.SubElement(run, "{urn:not-hancom}t")
    created.text = "도보네비"
    edited = etree.tostring(root, xml_declaration=True, encoding="UTF-8").decode("utf-8")
    src = tmp_path / "before.hwpx"
    sha = _write(src, bare)
    dst = tmp_path / "after.hwpx"
    _write(dst, edited)
    report = _compare(src, dst, [_target(2, None)], sha)
    assert report.ok is False and report.unexpected_count > 0
    wrong_local = etree.fromstring(bare.encode("utf-8"))
    other = list(iter_section_paragraphs(wrong_local))[2][0]
    foreign = etree.SubElement(other, "{http://www.hancom.co.kr/hwpml/2011/paragraph}nott")
    foreign.text = "도보네비"
    foreign_xml = etree.tostring(wrong_local, xml_declaration=True, encoding="UTF-8").decode("utf-8")
    foreign_path = tmp_path / "foreign.hwpx"
    _write(foreign_path, foreign_xml)
    foreign_report = _compare(src, foreign_path, [_target(2, None)], sha)
    assert foreign_report.ok is False and foreign_report.unexpected_count > 0


def test_walker_matches_structure_index_on_real_form() -> None:
    assert _REAL.is_file()
    before = _REAL.read_bytes()
    index = index_hwpx_structure(_REAL)
    assert _REAL.read_bytes() == before
    with zipfile.ZipFile(_REAL) as archive:
        root = etree.fromstring(archive.read(index.sections[0].section_member))
    walked = list(iter_section_paragraphs(root))
    assert len(walked) == len(index.sections[0].paragraphs)
    for element, record in zip(walked, index.sections[0].paragraphs):
        assert paragraph_raw_text(element) == record.raw_text


def test_real_form_compared_with_itself_has_no_diff() -> None:
    assert _REAL.is_file()
    sha = hashlib.sha256(_REAL.read_bytes()).hexdigest()
    report = compare_hwpx_xml_scope(_REAL, _REAL, [], expected_sha256=sha)
    assert report.ok is True and report.verdict == "PASS"
    assert report.changes == []
    assert report.unexpected_count == 0
