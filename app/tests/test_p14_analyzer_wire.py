# -*- coding: utf-8 -*-
"""P1.4-2: production HWPX publish calls the Analyzer for current grants only."""

from __future__ import annotations

import inspect
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from auto_write.models import ProjectInput, TemplateProfile
from auto_write.services import hwpx_submit as hs
from auto_write.services.hwpx_submit import submit_hwpx
from auto_write.services.project_service import ProjectService
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import assess_fields

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
    return f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'


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


def _paired_form(path: Path) -> None:
    _hwpx(path, [
        _section(_table([[_cell("기업명", 0, 0), _cell("", 0, 1)]])),
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


def test_production_functions_call_analyzer_grant_commit() -> None:
    submit_source = inspect.getsource(submit_hwpx)
    generate_source = inspect.getsource(ProjectService._generate_hwpx_direct)
    for source in (submit_source, generate_source):
        assert "authorize_t02_writes" in source
        assert "authorization_is_current" in source
        assert "commit_t02_label_writes" in source
    assert "fill_hwpx(" in submit_source
    assert "submit_hwpx(" in generate_source


def test_submit_writes_current_grant_and_holds_ungranted_eligible(tmp_path: Path) -> None:
    src = tmp_path / "paired.hwpx"
    _paired_form(src)
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    seen: list[dict[str, str]] = []
    real_commit = hs.commit_t02_label_writes

    def _spy(in_hwpx, out_hwpx, values):
        seen.append(dict(values))
        return real_commit(in_hwpx, out_hwpx, values)

    hs.commit_t02_label_writes = _spy
    try:
        report = submit_hwpx(
            src,
            out,
            identity={"기업명": "도보네비", "참고사항": "메모"},
            normalize_colors=False,
            submission_cleanup=False,
        )
    finally:
        hs.commit_t02_label_writes = real_commit

    assert seen == [{"기업명": "도보네비"}]
    final = Path(report.final)
    assert final.is_file()
    texts = _texts(final)
    assert "도보네비" in texts
    assert "메모" not in texts
    assert report.filled["기업명"] == "도보네비"
    assert "참고사항" in report.residual
    assert any(note == "[t02] 참고사항 AUTHORIZATION_PENDING" for note in report.notes)
    assert any(note == "[t02] 기업명 GRANT_WRITTEN" for note in report.notes)
    assert src.read_bytes() == before
    assert not list(tmp_path.glob("*.__t02_auth__.*"))

    source_index = index_hwpx_structure(src)
    pending = next(field for field in assess_fields(source_index) if field.field_label == "참고사항")
    granted = next(field for field in assess_fields(source_index) if field.field_label == "기업명")
    assert pending.eligible is True
    assert pending.decision == "REVIEW_REQUIRED"
    assert pending.review_reason == ("AUTHORIZATION_PENDING",)
    assert pending.auto_write_allowed is False
    assert granted.decision == "REVIEW_REQUIRED"
    assert granted.auto_write_allowed is False

    output_fields = assess_fields(index_hwpx_structure(final))
    output_pending = next(field for field in output_fields if field.field_label == "참고사항")
    assert output_pending.eligible is True
    assert output_pending.decision == "REVIEW_REQUIRED"
    assert output_pending.review_reason == ("AUTHORIZATION_PENDING",)
    assert output_pending.auto_write_allowed is False
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in output_fields)


def test_submit_refuses_grant_when_authorization_is_not_current(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "grant.hwpx"
    _hwpx(src, [_section(_table([[_cell("기업명", 0, 0), _cell("", 0, 1)]]))])
    monkeypatch.setattr(
        "core.docx.services.hwpx_protected_regions.authorization_is_current",
        lambda index, grant: False,
    )
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"기업명": "도보네비"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    final = Path(report.final)
    assert "도보네비" not in _texts(final)
    assert "기업명" in report.residual
    assert any("AUTHORIZATION_PENDING" in note for note in report.notes)
    fields = [field for field in assess_fields(index_hwpx_structure(src)) if field.field_label == "기업명"]
    assert fields[0].decision == "REVIEW_REQUIRED"
    assert fields[0].review_reason == ("AUTHORIZATION_PENDING",)
    assert fields[0].auto_write_allowed is False


def test_complete_synonym_identity_still_uses_legacy_fill(tmp_path: Path) -> None:
    src = tmp_path / "synonym.hwpx"
    _hwpx(src, [_section(_table([[_cell("상호", 0, 0), _cell("", 0, 1)]]))])
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(src, out, identity={"기업명": "도보네비(주)"}, normalize_colors=False, submission_cleanup=False)
    assert report.filled == {"기업명": "도보네비(주)"}
    assert "도보네비(주)" in _texts(Path(report.final))
    assert not any(note.endswith("GRANT_WRITTEN") for note in report.notes)


def test_generate_hwpx_direct_wires_grants_and_leaves_pending(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _paired_form(src)
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
        organization_profile={"name": "도보네비"},
        answers={"참고사항": "메모"},
        project_meta={},
    )
    bundle = service._generate_hwpx_direct("p1", profile, project_input)
    final = Path(bundle.output_hwpx)
    texts = _texts(final)
    assert "도보네비" in texts
    assert "메모" not in texts
    route = json.loads(Path(bundle.qa_report).read_text(encoding="utf-8"))
    assert route["t02_analyzer"]["written"] == ["기업명"]
    assert route["t02_analyzer"]["pending"] == ["참고사항"]
    assert route["routing"]["filled"]["기업명"] == "도보네비"
    assert "참고사항" in route["routing"]["residual"]
    assert "기업명" not in route["routing"]["residual"]
    output_dir = storage.project_dir("p1") / "output"
    assert list(output_dir.glob(".t02-auth-*")) == []
    output_fields = assess_fields(index_hwpx_structure(final))
    pending = next(field for field in output_fields if field.field_label == "참고사항")
    assert pending.decision == "REVIEW_REQUIRED"
    assert pending.review_reason == ("AUTHORIZATION_PENDING",)
    assert pending.auto_write_allowed is False
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in output_fields)
