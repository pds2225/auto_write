# -*- coding: utf-8 -*-
"""P1.4-1: Analyzer grants unlock writes only through the Analyzer commit API."""

from __future__ import annotations

import zipfile
from dataclasses import replace
from pathlib import Path

from auto_write.services.hwpx_fill import commit_t02_label_writes
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorization_is_current,
    authorize_t02_writes,
    t02_write_authorized,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _hpf(section_count: int = 1) -> str:
    items = "".join(
        f'<opf:item id="s{index}" href="Contents/section{index}.xml" media-type="application/xml"/>'
        for index in range(section_count)
    )
    refs = "".join(f'<opf:itemref idref="s{index}"/>' for index in range(section_count))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        f"<opf:manifest>{items}</opf:manifest><opf:spine>{refs}</opf:spine></opf:package>"
    )


def _cell(text: str, row: int, col: int, *, col_span: int = 1, runs: int = 1) -> str:
    if text:
        body = f"<hp:run><hp:t>{text}</hp:t></hp:run>"
    elif runs > 1:
        body = "".join("<hp:run><hp:t></hp:t></hp:run>" for _ in range(runs))
    else:
        body = "<hp:run></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>"
        + body
        + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + f'<hp:cellSpan rowSpan="1" colSpan="{col_span}"/></hp:tc>'
    )


def _table(rows: list[list[str]]) -> str:
    return "<hp:p><hp:run><hp:tbl>" + "".join(
        "<hp:tr>" + "".join(row) + "</hp:tr>" for row in rows
    ) + "</hp:tbl></hp:run></hp:p>"


def _section(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'


def _hwpx(path: Path, sections: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        for index, section in enumerate(sections):
            archive.writestr(f"Contents/section{index}.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf(len(sections)).encode("utf-8"))


def _texts(path: Path) -> list[str]:
    from lxml import etree

    with zipfile.ZipFile(path) as archive:
        roots = [etree.fromstring(archive.read(name)) for name in archive.namelist() if name.startswith("Contents/section")]
    return [node.text or "" for root in roots for node in root.iter(f"{{{_HP}}}t")]


def test_current_analyzer_grant_unlocks_commit_api_write(tmp_path: Path) -> None:
    src = tmp_path / "grant.hwpx"
    _hwpx(src, [_section(_table([[_cell("기업명", 0, 0), _cell("", 0, 1)]]))])

    index = index_hwpx_structure(src)
    fields = [field for field in assess_fields(index) if field.field_label == "기업명"]
    assert len(fields) == 1
    assert fields[0].eligible is True
    assert fields[0].decision == "REVIEW_REQUIRED"
    assert fields[0].review_reason == ("AUTHORIZATION_PENDING",)
    assert fields[0].auto_write_allowed is False
    assert t02_write_authorized(index, fields[0]) is True

    grants = authorize_t02_writes(index)
    assert [grant.field_label for grant in grants] == ["기업명"]
    assert authorization_is_current(index, grants[0]) is True
    assert authorization_is_current(index, replace(grants[0], row=99)) is False

    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "도보네비"})
    assert report.ok is True
    assert "도보네비" in _texts(dst)


def test_eligible_but_ungrantable_wide_cell_stays_pending_and_refused(tmp_path: Path) -> None:
    src = tmp_path / "wide.hwpx"
    _hwpx(src, [
        _section(""),
        _section(_table([[_cell("참고사항", 19, 1), _cell("", 19, 2, col_span=18, runs=2)]])),
    ])

    index = index_hwpx_structure(src)
    field = next(field for field in assess_fields(index) if field.field_label == "참고사항")
    assert field.field_type == "T02"
    assert field.eligible is True
    assert field.decision == "REVIEW_REQUIRED"
    assert field.review_reason == ("AUTHORIZATION_PENDING",)
    assert field.auto_write_allowed is False

    assert authorize_t02_writes(index) == ()
    assert t02_write_authorized(index, field) is False

    dst = tmp_path / "refused.hwpx"
    report = commit_t02_label_writes(src, dst, {"참고사항": "메모"})
    assert report.ok is False
    assert "NOT_AUTHORIZED:참고사항" in report.reasons
    assert not dst.exists()
