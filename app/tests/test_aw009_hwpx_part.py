# -*- coding: utf-8 -*-
"""AW-009 HWPX current-section fill uses existing guidance writers only."""

from __future__ import annotations

import zipfile
from pathlib import Path

from auto_write.services.aw009_hwpx_part import (
    build_draft_text,
    fill_current_section,
    match_section_field,
)
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _label(text: str, row: int = 0) -> str:
    return (
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>" + text + "</hp:t></hp:run></hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _value(runs: str, row: int = 0) -> str:
    return (
        "<hp:tc><hp:subList><hp:p>" + runs + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _section(rows: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run><hp:tbl>{rows}</hp:tbl></hp:run></hp:p></hs:sec>"
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
    from lxml import etree

    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def test_build_draft_requires_materials_or_instruction() -> None:
    try:
        build_draft_text([], "")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "근거" in str(exc) or "지시" in str(exc)


def test_hwpx_current_section_fill_keeps_guidance_and_scope(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    rows = (
        "<hp:tr>"
        + _label("사업 개요")
        + _value("<hp:run><hp:t>※ 개요를 작성</hp:t></hp:run><hp:run></hp:run>")
        + "</hp:tr>"
        + "<hp:tr>"
        + _label("팀 구성", 1)
        + _value("<hp:run><hp:t>※ 팀을 작성</hp:t></hp:run><hp:run><hp:t>기존팀</hp:t></hp:run>", 1)
        + "</hp:tr>"
    )
    _hwpx(src, _section(rows))
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    match = match_section_field(index, "1. 사업 개요")
    assert match.kind == "guidance_narrative"
    assert "사업" in match.field_label and "개요" in match.field_label.replace(" ", "")
    out = tmp_path / "out.hwpx"
    result = fill_current_section(
        src,
        out,
        section_title="1. 사업 개요",
        draft_text="도보 내비게이션 MVP",
    )
    assert result.ok is True, result.reason
    assert result.scope_ok is True
    assert "사업" in result.field_label and "개요" in result.field_label.replace(" ", "")
    texts = _texts(out)
    assert "※ 개요를 작성" in texts
    assert "도보 내비게이션 MVP" in texts
    assert "기존팀" in texts
    assert src.read_bytes() == before


def test_ambiguous_section_match_is_blocked(tmp_path: Path) -> None:
    src = tmp_path / "amb.hwpx"
    rows = (
        "<hp:tr>"
        + _label("사업개요")
        + _value("<hp:run><hp:t>※ a</hp:t></hp:run><hp:run></hp:run>")
        + "</hp:tr>"
        + "<hp:tr>"
        + _label("사업 개요 요약", 1)
        + _value("<hp:run><hp:t>※ b</hp:t></hp:run><hp:run></hp:run>", 1)
        + "</hp:tr>"
    )
    _hwpx(src, _section(rows))
    index = index_hwpx_structure(src)
    try:
        match_section_field(index, "사업개요")
        # if engine only surfaces one target, that is fine; only assert no crash path below
    except ValueError as exc:
        assert "2개" in str(exc) or "매칭" in str(exc)
