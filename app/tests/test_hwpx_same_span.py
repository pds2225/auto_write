# -*- coding: utf-8 -*-
"""Same cell/paragraph run and character-span fill.

A fillable value or a label-adjacent blank that crosses hp:t nodes must not
overwrite a sibling run, collapse that span into the first node, or stay
silent. Cross-span skips stay in residual and ``[span] … UNFILLED``.
A blank that sits wholly inside one hp:t still fills, and sibling runs stay.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes, fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorize_t02_writes,
    find_t02_auto_targets,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" '
        'media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _hwpx(path: Path, section: str) -> None:
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="3">'
        '<hh:charPr id="0" textColor="000000"/>'
        '<hh:charPr id="2" textColor="000000"/>'
        '<hh:charPr id="5" textColor="000000"/>'
        "</hh:charProperties></hh:refList></hh:head>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header.encode("utf-8"))
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))


def _sec(body: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _runs(path: Path) -> list[tuple[str, list[str]]]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    found = []
    for run in root.iter(f"{{{_HP}}}run"):
        if any(etree.QName(child).localname == "tbl" for child in run):
            continue
        texts = [
            node.text or ""
            for node in run
            if etree.QName(node).localname == "t"
        ]
        found.append((run.get("charPrIDRef") or "", texts))
    return found


def _fill(tmp_path: Path, name: str, body: str, identity: dict[str, str]):
    src = tmp_path / f"{name}.hwpx"
    out = tmp_path / f"{name}-out.hwpx"
    _hwpx(src, _sec(body))
    before = src.read_bytes()
    report = fill_hwpx(src, out, identity=identity)
    assert src.read_bytes() == before
    return src, out, report


def _no_auto(path: Path) -> None:
    index = index_hwpx_structure(path)
    assert find_t02_auto_targets(index) == ()
    assert authorize_t02_writes(index) == ()
    assert all(
        field.decision != "AUTO" and field.auto_write_allowed is False
        for field in assess_fields(index)
    )


def test_split_placeholder_keeps_sibling_unit(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>매출</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>000</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>억원</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "split-unit", body, {"매출": "12"})
    assert _runs(out) == _runs(src)
    assert report.filled == {}
    assert "매출" in report.residual
    assert "[span] 매출 row=0 col=1 UNFILLED" in report.notes
    _no_auto(src)
    refused = tmp_path / "refused.hwpx"
    commit = commit_t02_label_writes(src, refused, {"매출": "12"})
    assert commit.ok is False
    assert not refused.exists()


def test_placeholder_in_later_run_is_not_merged_forward(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>매출</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>000억원</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "tail", body, {"매출": "12"})
    assert _runs(out) == [("2", ["매출"]), ("0", [""]), ("5", ["000억원"])]
    assert _runs(out) == _runs(src)
    assert "12" not in "".join(text for _ref, texts in _runs(out) for text in texts)
    assert "매출" in report.residual
    assert "[span] 매출 row=0 col=1 UNFILLED" in report.notes
    _no_auto(src)


def test_single_node_placeholder_still_fills(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>매출</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="5"><hp:t>000억원</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    _src, out, report = _fill(tmp_path, "one-node", body, {"매출": "12"})
    assert _runs(out) == [("2", ["매출"]), ("5", ["12"])]
    assert report.filled == {"매출": "12"}
    assert "매출" not in report.residual
    assert not any(note.startswith("[span]") for note in report.notes)


def test_label_adjacency_crossing_runs_is_noted(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="2"><hp:t>기업명 : </hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>______</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "adj", body, {"기업명": "도보네비"})
    assert _runs(out) == [("2", ["기업명 : "]), ("0", ["______"])]
    assert _runs(out) == _runs(src)
    assert report.filled == {}
    assert "기업명" in report.residual
    assert "[span] 기업명 row=0 col=0 UNFILLED" in report.notes
    _no_auto(src)


def test_same_run_character_spans_are_not_merged(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>기업명 : ___</hp:t><hp:t>___</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "chars", body, {"기업명": "도보네비"})
    assert _runs(out) == [("0", ["기업명 : ___", "___"])]
    assert _runs(out) == _runs(src)
    assert "기업명" in report.residual
    assert "[span] 기업명 row=0 col=0 UNFILLED" in report.notes


def test_blank_wholly_inside_sibling_run_fills_that_run_only(tmp_path: Path) -> None:
    body = """<hp:p>
<hp:run charPrIDRef="2"><hp:t>기업명</hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t> : ______</hp:t></hp:run>
</hp:p>"""
    _src, out, report = _fill(tmp_path, "whole", body, {"기업명": "도보네비"})
    assert _runs(out) == [("2", ["기업명"]), ("0", [" : 도보네비"])]
    assert report.filled == {"기업명": "도보네비"}
    assert "기업명" not in report.residual
    assert not any(note.startswith("[span]") for note in report.notes)


def test_checkbox_mark_keeps_sibling_option_run(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>사업자형태</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>□</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>개인 </hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>□</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>법인</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    _src, out, report = _fill(tmp_path, "check", body, {"사업자형태": "개인"})
    assert _runs(out) == [
        ("2", ["사업자형태"]),
        ("0", ["■"]),
        ("5", ["개인 "]),
        ("0", ["□"]),
        ("5", ["법인"]),
    ]
    assert report.filled == {"사업자형태": "개인"}
    assert not any(note.startswith("[span]") for note in report.notes)


def test_empty_sibling_runs_still_fill_the_first_node(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t></hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "empty2", body, {"기업명": "도보네비"})
    assert _runs(out) == [("2", ["기업명"]), ("0", ["도보네비"]), ("5", [""])]
    assert report.filled == {"기업명": "도보네비"}
    assert not any(note.startswith("[span]") for note in report.notes)
    _no_auto(src)


def test_split_label_text_still_fills_the_empty_value_cell(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="2"><hp:t>기</hp:t></hp:run>
<hp:run charPrIDRef="2"><hp:t>업명</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "label-split", body, {"기업명": "도보네비"})
    assert _runs(out) == [("2", ["기"]), ("2", ["업명"]), ("0", ["도보네비"])]
    assert report.filled == {"기업명": "도보네비"}
    assert not any(note.startswith("[span]") for note in report.notes)
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["기업명"]
    assert [item.field_label for item in authorize_t02_writes(index)] == ["기업명"]
    assert all(
        field.decision != "AUTO" and field.auto_write_allowed is False
        for field in assess_fields(index)
    )


def test_unit_sibling_is_not_wiped(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>매출</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>원</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "unit", body, {"매출": "12"})
    assert _runs(out) == _runs(src)
    assert "매출" in report.residual
    assert not any(note.startswith("[span]") for note in report.notes)


def test_set_cell_text_refuses_split_spans() -> None:
    from auto_write.services.hwpx_fill import _set_cell_text

    xml = (
        f'<hp:tc xmlns:hp="{_HP}"><hp:subList><hp:p>'
        '<hp:run charPrIDRef="0"><hp:t>000</hp:t></hp:run>'
        '<hp:run charPrIDRef="5"><hp:t>억원</hp:t></hp:run>'
        "</hp:p></hp:subList></hp:tc>"
    )
    cell = etree.fromstring(xml)
    assert _set_cell_text(cell, "12") is False
    texts = [node.text for node in cell.iter(f"{{{_HP}}}t")]
    refs = [node.get("charPrIDRef") for node in cell.iter(f"{{{_HP}}}run")]
    assert texts == ["000", "억원"]
    assert refs == ["0", "5"]


def test_line_edit_cell_notes_split_span(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>앵커문구</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>000</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>억원</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src = tmp_path / "edit.hwpx"
    out = tmp_path / "edit-out.hwpx"
    _hwpx(src, _sec(body))
    report = fill_hwpx(src, out, line_edits=[{"anchor": "앵커문구", "cells": {"1": "12"}}])
    assert _runs(out) == _runs(src)
    assert any("run 경계 분할" in note and "colAddr=1" in note for note in report.notes)


def test_submit_reports_split_span_without_writing(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>매출</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>000</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>억원</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src = tmp_path / "submit.hwpx"
    out = tmp_path / "submit-out.hwpx"
    _hwpx(src, _sec(body))
    before = src.read_bytes()
    report = submit_hwpx(
        src,
        out,
        identity={"매출": "12"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    final = Path(report.final)
    assert src.read_bytes() == before
    assert _runs(final) == [("2", ["매출"]), ("0", ["000"]), ("5", ["억원"])]
    assert "매출" in report.residual
    assert "[span] 매출 row=0 col=1 UNFILLED" in report.notes
    assert not any("매출" in note and note.endswith("GRANT_WRITTEN") for note in report.notes)
    _no_auto(final)
