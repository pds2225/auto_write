# -*- coding: utf-8 -*-
"""P0-3: an exact target write may change only that hp:t.

These fixtures name coordinates directly. They do not choose fields.

Legacy paths that still replace a wider unit, and are not this command:

- ``_set_cell_text`` (hwpx_fill.py): writes the first hp:t and clears the other
  hp:t nodes in the cell, may retarget charPr, and drops that cell's linesegarray.
  Used by ``fill_hwpx`` label fill. Not used by ``commit_exact_text_writes``.
- ``_apply_line_edits``: ``set`` replaces a whole paragraph, and ``nth``/``all``
  select paragraphs by substring. Explicit legacy edits only.
- ``_fill_inline_fields_in_p``: matches a label inside one paragraph. A span that
  crosses two hp:t nodes returns False. Legacy fill only.
- ``fill_hwpx``: saves the matches it could apply. The exact-target command
  cancels the whole plan before mutation instead.

Action: the exact command refuses a non-empty node, a coordinate miss, a hash
miss, and any post-write XML change outside the named nodes. The legacy
functions stay so F01 and fill_hwpx keep their current behavior.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import ExactTextTarget, commit_exact_text_writes
from core.docx.services.hwpx_xml_scope_diff import (
    XmlScopeTarget,
    compare_hwpx_xml_scope,
    iter_section_paragraphs,
    run_raw_text,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _package(path: Path) -> str:
    section0 = f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">
  <hp:p><hp:run charPrIDRef="1"><hp:t>중복문구</hp:t></hp:run></hp:p>
  <hp:p><hp:run charPrIDRef="1"><hp:tbl>
    <hp:tr>
      <hp:tc>
        <hp:subList>
          <hp:p paraPrIDRef="3">
            <hp:run charPrIDRef="2"><hp:t>기업명</hp:t></hp:run>
            <hp:run charPrIDRef="4"><hp:t></hp:t></hp:run>
          </hp:p>
        </hp:subList>
        <hp:cellAddr rowAddr="0" colAddr="0"/>
        <hp:cellSpan rowSpan="1" colSpan="1"/>
      </hp:tc>
      <hp:tc>
        <hp:subList>
          <hp:p paraPrIDRef="5"><hp:run charPrIDRef="6"><hp:t>※ 안내문입니다</hp:t></hp:run></hp:p>
          <hp:p paraPrIDRef="8"><hp:run charPrIDRef="7"><hp:t></hp:t></hp:run></hp:p>
          <hp:p><hp:run charPrIDRef="1"><hp:tbl>
            <hp:tr><hp:tc>
              <hp:subList><hp:p><hp:run charPrIDRef="9"><hp:t>중첩표</hp:t></hp:run></hp:p></hp:subList>
              <hp:cellAddr rowAddr="0" colAddr="0"/>
              <hp:cellSpan rowSpan="1" colSpan="1"/>
            </hp:tc></hp:tr>
          </hp:tbl></hp:run></hp:p>
        </hp:subList>
        <hp:cellAddr rowAddr="0" colAddr="1"/>
        <hp:cellSpan rowSpan="1" colSpan="1"/>
      </hp:tc>
    </hp:tr>
    <hp:tr>
      <hp:tc>
        <hp:subList><hp:p><hp:run charPrIDRef="1"><hp:t>중복문구</hp:t></hp:run></hp:p></hp:subList>
        <hp:cellAddr rowAddr="1" colAddr="0"/>
        <hp:cellSpan rowSpan="1" colSpan="1"/>
      </hp:tc>
      <hp:tc>
        <hp:subList><hp:p paraPrIDRef="8"><hp:run charPrIDRef="7"><hp:t></hp:t></hp:run></hp:p></hp:subList>
        <hp:cellAddr rowAddr="1" colAddr="1"/>
        <hp:cellSpan rowSpan="1" colSpan="1"/>
      </hp:tc>
    </hp:tr>
  </hp:tbl></hp:run></hp:p>
  <hs:note>바닥글고정</hs:note>
</hs:sec>
"""
    section1 = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run><hp:t>다른섹션</hp:t></hp:run></hp:p></hs:sec>'
    )
    header = '<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" page="1">HEADER</hh:head>'
    hpf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest>'
        '<opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/>'
        '<opf:item id="s1" href="Contents/section1.xml" media-type="application/xml"/>'
        '</opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/><opf:itemref idref="s1"/></opf:spine>'
        '</opf:package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header.encode("utf-8"))
        archive.writestr("Contents/section0.xml", section0.encode("utf-8"))
        archive.writestr("Contents/section1.xml", section1.encode("utf-8"))
        archive.writestr("Contents/content.hpf", hpf.encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paragraph_runs(path: Path) -> list[tuple[str, list[tuple[str, str]]]]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    found = []
    for paragraph in iter_section_paragraphs(root):
        runs = []
        for child in paragraph:
            if not str(child.tag).endswith("run"):
                continue
            runs.append((child.get("charPrIDRef") or "", run_raw_text(child)))
        found.append((paragraph.get("paraPrIDRef") or "", runs))
    return found


def _member(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def _target(paragraph: int, run: int, text_node: int, expected: str, value: str, **coords) -> ExactTextTarget:
    return ExactTextTarget(
        "Contents/section0.xml", paragraph, run, text_node, expected, value,
        table_index=coords.get("table_index"), row=coords.get("row"), col=coords.get("col"),
    )


def _write(src: Path, dst: Path, sha: str, targets: list[ExactTextTarget]):
    before = src.read_bytes()
    report = commit_exact_text_writes(src, dst, targets, source_sha256=sha)
    assert src.read_bytes() == before
    return report


def test_exact_text_node_keeps_guidance_label_and_nested_table(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    sha = _package(src)
    before = _paragraph_runs(src)
    dst = tmp_path / "out.hwpx"
    report = _write(src, dst, sha, [
        _target(4, 0, 0, "", "도보네비", table_index=0, row=0, col=1),
        _target(2, 1, 0, "", "옆칸", table_index=0, row=0, col=0),
    ])
    assert report.ok is True and report.cancelled is False and report.written_count == 2
    after = _paragraph_runs(dst)
    assert after[3][1][0][1] == "※ 안내문입니다"
    assert after[3][0] == before[3][0]
    assert after[3][1][0][0] == before[3][1][0][0]
    assert after[2][1][0] == ("2", "기업명")
    assert after[2][1][1] == ("4", "옆칸")
    assert after[4][1][0] == ("7", "도보네비")
    assert after[4][0] == "8"
    assert after[6][1][0][1] == "중첩표"
    assert after[0][1][0][1] == "중복문구"
    assert after[7][1][0][1] == "중복문구"
    assert _member(src, "Contents/header.xml") == _member(dst, "Contents/header.xml")
    assert _member(src, "Contents/section1.xml") == _member(dst, "Contents/section1.xml")
    assert b"\xeb\xb0\x94\xeb\x8b\xa5\xea\xb8\x80\xea\xb3\xa0\xec\xa0\x95" in _member(dst, "Contents/section0.xml") or "바닥글고정".encode("utf-8") in _member(dst, "Contents/section0.xml")
    diff = compare_hwpx_xml_scope(
        src, dst,
        [
            XmlScopeTarget("Contents/section0.xml", 4, 0, 0),
            XmlScopeTarget("Contents/section0.xml", 2, 1, 0),
        ],
        expected_sha256=sha,
    )
    assert diff.ok is True and diff.unexpected_count == 0


def test_duplicate_string_changes_only_the_named_target(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    sha = _package(src)
    dst = tmp_path / "out.hwpx"
    report = _write(src, dst, sha, [_target(8, 0, 0, "", "둘째만", table_index=0, row=1, col=1)])
    assert report.ok is True
    runs = _paragraph_runs(dst)
    assert runs[0][1][0][1] == "중복문구"
    assert runs[7][1][0][1] == "중복문구"
    assert runs[8][1][0][1] == "둘째만"
    assert runs[4][1][0][1] == ""


def test_precondition_failures_write_nothing(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    sha = _package(src)
    original = src.read_bytes()
    dst = tmp_path / "out.hwpx"
    cases = [
        ("sha", commit_exact_text_writes(src, dst, [_target(4, 0, 0, "", "값")], source_sha256="0" * 64), "SHA_MISMATCH"),
        ("text", _write(src, dst, sha, [_target(4, 0, 0, "다른글", "값")]), "EXPECTED_TEXT_MISMATCH"),
        ("coord", _write(src, dst, sha, [_target(4, 0, 0, "", "값", table_index=0, row=9, col=9)]), "COORDINATE_MISMATCH"),
        ("partial", _write(src, dst, sha, [
            _target(4, 0, 0, "", "값", table_index=0, row=0, col=1),
            _target(8, 0, 0, "없는값", "값", table_index=0, row=1, col=1),
        ]), "EXPECTED_TEXT_MISMATCH"),
    ]
    for _name, report, reason in cases:
        assert report.ok is False and report.cancelled is True, _name
        assert report.reason.startswith(reason), (_name, report.reason)
        assert not dst.exists()
        assert src.read_bytes() == original


def test_post_validation_failure_leaves_no_final_output(tmp_path: Path, monkeypatch) -> None:
    from core.docx.services.hwpx_xml_scope_diff import XmlScopeDiffReport
    src = tmp_path / "form.hwpx"
    sha = _package(src)
    original = src.read_bytes()
    dst = tmp_path / "out.hwpx"
    target = _target(4, 0, 0, "", "값", table_index=0, row=0, col=1)

    def mutated(*_args, **_kwargs):
        src.write_bytes(src.read_bytes() + b"Z")
        return XmlScopeDiffReport(True, "PASS", sha, sha, True, True)

    def broken(*_args, **_kwargs):
        raise RuntimeError("scope boom")

    def rejected(*_args, **_kwargs):
        return XmlScopeDiffReport(False, "OUT_OF_SCOPE_XML_CHANGE", sha, sha, True, True)

    monkeypatch.setattr("core.docx.services.hwpx_xml_scope_diff.compare_hwpx_xml_scope", mutated)
    report = commit_exact_text_writes(src, dst, [target], source_sha256=sha)
    assert report.ok is False and report.reason == "SOURCE_MUTATED"
    assert not dst.exists()
    src.write_bytes(original)

    monkeypatch.setattr("core.docx.services.hwpx_xml_scope_diff.compare_hwpx_xml_scope", broken)
    report = commit_exact_text_writes(src, dst, [target], source_sha256=sha)
    assert report.ok is False and report.reason == "XML_SCOPE_ERROR"
    assert not dst.exists()
    assert src.read_bytes() == original

    monkeypatch.setattr("core.docx.services.hwpx_xml_scope_diff.compare_hwpx_xml_scope", rejected)
    report = commit_exact_text_writes(src, dst, [target], source_sha256=sha)
    assert report.ok is False and report.reason == "OUT_OF_SCOPE_XML_CHANGE"
    assert not dst.exists()

    monkeypatch.undo()
    report = commit_exact_text_writes(src, dst, [target], source_sha256=sha)
    assert report.ok is True and dst.is_file()
    assert src.read_bytes() == original
