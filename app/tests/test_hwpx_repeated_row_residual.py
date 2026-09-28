# -*- coding: utf-8 -*-
"""FINDING-QA-002: a repeated label's second empty value cell stays in residual.

The legacy writer may fill only the first empty value. Residual reporting must
still name the unfilled later row, without writing that cell or granting AUTO.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from auto_write.models import ProjectInput, TemplateProfile
from auto_write.services.hwpx_fill import commit_t02_label_writes, fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx
from auto_write.services.project_service import ProjectService
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorize_t02_writes,
    document_duplicate_unfilled_cells,
    find_t02_auto_targets,
    repeated_row_unfilled_cells,
    t02_write_authorized,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"


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
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _hwpx(path: Path, sections: list[str]) -> None:
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="1">'
        '<hh:charPr id="0" textColor="000000"/>'
        "</hh:charProperties></hh:refList></hh:head>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header.encode("utf-8"))
        for index, section in enumerate(sections):
            archive.writestr(f"Contents/section{index}.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf(len(sections)).encode("utf-8"))


def _texts(path: Path) -> list[str]:
    from lxml import etree

    with zipfile.ZipFile(path) as archive:
        roots = [
            etree.fromstring(archive.read(name))
            for name in archive.namelist()
            if name.startswith("Contents/section")
        ]
    return [node.text or "" for root in roots for node in root.iter(f"{{{_HP}}}t")]


def _repeated_form(path: Path) -> None:
    _hwpx(path, [
        _section(_table([
            [_cell("기업명", 0, 0), _cell("", 0, 1)],
            [_cell("기업명", 1, 0), _cell("", 1, 1)],
        ])),
        _section(_table([[_cell("참고사항", 19, 1), _cell("", 19, 2, col_span=18, runs=2)]])),
    ])


class _Storage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def project_dir(self, project_id: str) -> Path:
        path = self.root / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def results_dir(self, project_id: str) -> Path:
        path = self.project_dir(project_id) / "results"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def template_dir(self, template_id: str) -> Path:
        path = self.root / "templates" / template_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_project_input(self, project_id: str, project_input: ProjectInput) -> None:
        self.saved = project_input


def test_fill_reports_second_repeated_row_without_writing_it(tmp_path: Path) -> None:
    src = tmp_path / "repeated.hwpx"
    _hwpx(src, [_section(_table([
        [_cell("기업명", 0, 0), _cell("", 0, 1)],
        [_cell("기업명", 1, 0), _cell("", 1, 1)],
    ]))])
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(src, out, identity={"기업명": "첫번째"})
    texts = _texts(out)
    assert texts.count("기업명") == 2
    assert texts.count("첫번째") == 1
    assert report.filled == {"기업명": "첫번째"}
    assert "기업명" in report.residual
    assert ("기업명", 1, 1) in repeated_row_unfilled_cells(index_hwpx_structure(out))


def test_repeated_row_second_empty_is_residual_and_not_auto(tmp_path: Path) -> None:
    src = tmp_path / "repeated.hwpx"
    _repeated_form(src)
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"기업명": "첫번째", "참고사항": "메모"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    final = Path(report.final)
    texts = _texts(final)
    assert texts.count("기업명") == 2
    assert texts.count("첫번째") == 1
    assert "메모" not in texts
    assert src.read_bytes() == before

    assert "기업명" in report.residual
    assert "참고사항" in report.residual
    assert any(note == "[repeated-row] 기업명 row=1 col=1 UNFILLED" for note in report.notes)
    assert any(note == "[t02] 참고사항 AUTHORIZATION_PENDING" for note in report.notes)
    assert not any("기업명" in note and note.endswith("GRANT_WRITTEN") for note in report.notes)

    output_index = index_hwpx_structure(final)
    assert ("기업명", 1, 1) in repeated_row_unfilled_cells(output_index)
    unfilled = [
        field for field in assess_fields(output_index)
        if "REPEATED_ROW_UNFILLED" in field.review_reason
    ]
    assert any(
        field.field_label == "기업명" and field.row == 1 and field.col == 1 and field.content_state == "EMPTY"
        for field in unfilled
    )
    assert all(
        field.decision == "REVIEW_REQUIRED" and field.auto_write_allowed is False and field.eligible is False
        for field in unfilled
    )
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(output_index))
    assert all(
        not (target.field_label == "기업명" and target.row == 1)
        for target in find_t02_auto_targets(output_index)
    )
    assert all(
        not (grant.field_label == "기업명" and grant.row == 1)
        for grant in authorize_t02_writes(output_index)
    )
    pending = next(field for field in assess_fields(output_index) if field.field_label == "참고사항")
    assert pending.decision == "REVIEW_REQUIRED"
    assert pending.review_reason == ("AUTHORIZATION_PENDING",)
    assert pending.auto_write_allowed is False


def test_both_empty_repeated_rows_stay_review_until_one_value_is_filled(tmp_path: Path) -> None:
    src = tmp_path / "blank.hwpx"
    _hwpx(src, [_section(_table([
        [_cell("기업명", 0, 0), _cell("", 0, 1)],
        [_cell("기업명", 1, 0), _cell("", 1, 1)],
    ]))])
    index = index_hwpx_structure(src)
    assert repeated_row_unfilled_cells(index) == ()
    assert find_t02_auto_targets(index) == ()
    assert authorize_t02_writes(index) == ()
    blanks = [
        field for field in assess_fields(index)
        if field.field_label == "기업명" and field.content_state == "EMPTY"
    ]
    assert {(field.row, field.col) for field in blanks} == {(0, 1), (1, 1)}
    assert all("REPEATED_ROW_UNFILLED" in field.review_reason for field in blanks)
    assert all(
        field.decision == "REVIEW_REQUIRED" and field.auto_write_allowed is False and field.eligible is False
        for field in blanks
    )


def test_unique_label_fill_is_not_reported_as_repeated_residual(tmp_path: Path) -> None:
    src = tmp_path / "unique.hwpx"
    _hwpx(src, [_section(_table([[_cell("기업명", 0, 0), _cell("", 0, 1)]]))])
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"기업명": "첫번째"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    assert _texts(Path(report.final)).count("첫번째") == 1
    assert "기업명" not in report.residual
    assert not any(note.startswith("[repeated-row]") for note in report.notes)
    fields = assess_fields(index_hwpx_structure(Path(report.final)))
    assert not any("REPEATED_ROW_UNFILLED" in field.review_reason for field in fields)
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)


def test_generate_hwpx_direct_keeps_repeated_row_residual(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _repeated_form(src)
    storage = _Storage(tmp_path / "store")
    service = ProjectService(storage, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
    profile = TemplateProfile(
        template_id="tpl",
        template_name="tpl",
        source_docx=str(src),
        source_hwpx=str(src),
    )
    project_input = ProjectInput(
        template_id="tpl",
        organization_profile={"name": "첫번째"},
        answers={"참고사항": "메모"},
        project_meta={},
    )
    bundle = service._generate_hwpx_direct("p-repeat", profile, project_input)
    final = Path(bundle.output_hwpx)
    texts = _texts(final)
    assert texts.count("기업명") == 2
    assert texts.count("첫번째") == 1
    assert "메모" not in texts
    route = json.loads(Path(bundle.qa_report).read_text(encoding="utf-8"))
    assert "기업명" in route["routing"]["residual"]
    assert "참고사항" in route["routing"]["residual"]
    assert any(
        note == "[repeated-row] 기업명 row=1 col=1 UNFILLED"
        for note in route["routing"]["notes"]
    )
    output_fields = assess_fields(index_hwpx_structure(final))
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in output_fields)
    pending = next(field for field in output_fields if field.field_label == "참고사항")
    assert pending.review_reason == ("AUTHORIZATION_PENDING",)


def _company_row() -> str:
    return _table([[_cell("기업명", 0, 0), _cell("", 0, 1)]])


def _assert_duplicate_empty_label_gets_no_grant(src: Path, tmp_path: Path, expected_cells: set[tuple]) -> None:
    """Same empty label in two places: zero grants, zero writes, both cells reported."""
    index = index_hwpx_structure(src)
    targets = [target for target in find_t02_auto_targets(index) if target.field_label == "기업명"]
    assert len(targets) == 2
    fields = [
        field for field in assess_fields(index)
        if field.field_label == "기업명" and field.field_type == "T02"
    ]
    assert len(fields) == 2
    assert all(
        field.decision == "REVIEW_REQUIRED"
        and field.review_reason == ("AUTHORIZATION_PENDING",)
        and field.auto_write_allowed is False
        and field.eligible is True
        for field in fields
    )
    assert repeated_row_unfilled_cells(index) == ()
    assert [grant for grant in authorize_t02_writes(index) if grant.field_label == "기업명"] == []
    assert all(t02_write_authorized(index, field) is False for field in fields)

    refused = tmp_path / "refused.hwpx"
    commit = commit_t02_label_writes(src, refused, {"기업명": "첫번째"})
    assert commit.ok is False
    assert "NOT_AUTHORIZED:기업명" in commit.reasons
    assert not refused.exists()

    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"기업명": "첫번째"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    final = Path(report.final)
    texts = _texts(final)
    assert texts.count("기업명") == 2
    assert "첫번째" not in texts
    assert "기업명" in report.residual
    assert any(note == "[t02] 기업명 AUTHORIZATION_PENDING" for note in report.notes)
    assert not any("기업명" in note and note.endswith("GRANT_WRITTEN") for note in report.notes)
    assert repeated_row_unfilled_cells(index_hwpx_structure(final)) == ()
    leftover = document_duplicate_unfilled_cells(index_hwpx_structure(final))
    assert set(leftover) == expected_cells
    for label, section_index, table_index, row, col in expected_cells:
        note = (
            f"[duplicate-label] {label} section={section_index} "
            f"table={table_index} row={row} col={col} UNFILLED"
        )
        assert note in report.notes
    output_fields = [
        field for field in assess_fields(index_hwpx_structure(final))
        if field.field_label == "기업명" and field.field_type == "T02"
    ]
    assert len(output_fields) == 2
    assert all(
        field.decision == "REVIEW_REQUIRED"
        and field.review_reason == ("AUTHORIZATION_PENDING",)
        and field.auto_write_allowed is False
        for field in output_fields
    )


def test_two_tables_duplicate_empty_label_gets_zero_grants(tmp_path: Path) -> None:
    src = tmp_path / "two-tables.hwpx"
    _hwpx(src, [_section(_company_row() + _company_row())])
    _assert_duplicate_empty_label_gets_no_grant(
        src,
        tmp_path,
        {("기업명", 0, 0, 0, 1), ("기업명", 0, 1, 0, 1)},
    )


def test_two_sections_duplicate_empty_label_gets_zero_grants(tmp_path: Path) -> None:
    src = tmp_path / "two-sections.hwpx"
    _hwpx(src, [_section(_company_row()), _section(_company_row())])
    _assert_duplicate_empty_label_gets_no_grant(
        src,
        tmp_path,
        {("기업명", 0, 0, 0, 1), ("기업명", 1, 1, 0, 1)},
    )
