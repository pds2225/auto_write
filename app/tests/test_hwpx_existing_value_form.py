# -*- coding: utf-8 -*-
"""A form that already has values keeps those values and still fills empty cells."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import assess_fields, find_t02_auto_targets
from core.docx.services.hwpx_xml_scope_diff import XmlScopeTarget, compare_hwpx_xml_scope, sha256_file

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_DATA = Path(__file__).resolve().parents[2] / "data"
_FORM = "(서식09) 연구개발기관 대표의 참여의사 확인서_접수번호(기관명).hwpx"


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _cell(text: str, row: int, col: int) -> str:
    body = f"<hp:run><hp:t>{text}</hp:t></hp:run>" if text else "<hp:run></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>" + body + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + '<hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _hwpx(path: Path, section: str) -> None:
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="1">'
        '<hh:charPr id="0" textColor="000000"/></hh:charProperties></hh:refList></hh:head>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header.encode("utf-8"))
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.startswith("Contents/section")]
        roots = [etree.fromstring(archive.read(name)) for name in names]
    return [node.text or "" for root in roots for node in root.iter(f"{{{_HP}}}t")]


def _mixed() -> str:
    rows = (
        "<hp:tr>" + _cell("기업명", 0, 0) + _cell("기존회사", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("주소", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run><hp:tbl>{rows}</hp:tbl></hp:run></hp:p></hs:sec>"
    )


def test_empty_cell_is_filled_and_existing_value_stays(tmp_path: Path) -> None:
    src = tmp_path / "mixed.hwpx"
    _hwpx(src, _mixed())
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["주소"]
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
    replaced = tmp_path / "replaced.hwpx"
    refused = commit_t02_label_writes(src, replaced, {"기업명": "새회사"})
    assert refused.ok is False and not replaced.exists()
    both = tmp_path / "both.hwpx"
    assert commit_t02_label_writes(src, both, {"기업명": "새회사", "주소": "서울"}).ok is False
    assert not both.exists() and src.read_bytes() == before
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"주소": "서울"})
    assert report.ok is True
    assert "기존회사" in _texts(dst) and "서울" in _texts(dst) and "새회사" not in _texts(dst)
    assert src.read_bytes() == before


def test_submit_keeps_existing_value_on_a_mixed_form(tmp_path: Path) -> None:
    src = tmp_path / "mixed.hwpx"
    _hwpx(src, _mixed())
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src, out,
        identity={"기업명": "새회사", "주소": "서울"},
        normalize_colors=False, submission_cleanup=False,
    )
    texts = _texts(Path(report.final))
    assert "서울" in texts
    assert "기존회사" in texts
    assert "새회사" not in texts
    assert src.read_bytes() == before


def test_real_hwpx_existing_value_qualification(tmp_path: Path) -> None:
    source = _DATA / _FORM
    assert source.is_file()
    before = source.read_bytes()
    sample = tmp_path / "sample.hwpx"
    shutil.copyfile(source, sample)
    original_texts = [text for text in _texts(sample) if text.strip()]
    index = index_hwpx_structure(sample)
    targets = [item for item in find_t02_auto_targets(index) if item.expected_raw_text == ""]
    assert targets
    label = targets[0].field_label
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: "기존값확인"})
    assert report.ok is True
    assert sample.read_bytes() == source.read_bytes() == before
    after = _texts(dst)
    assert "기존값확인" in after
    assert all(text in after for text in original_texts)
    diff = compare_hwpx_xml_scope(
        sample, dst,
        [XmlScopeTarget(targets[0].section_member, targets[0].paragraph_index, targets[0].run_index, targets[0].text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0
    blocked = tmp_path / "blocked.hwpx"
    assert commit_t02_label_writes(dst, blocked, {label: "다시씀"}).ok is False
    assert not blocked.exists()
    assert _texts(dst).count("기존값확인") == 1
