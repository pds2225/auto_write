# -*- coding: utf-8 -*-
"""Nested tables: write a leaf cell, never the cell that contains the table."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import replace
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    _compact,
    _sign_consent_label,
    assess_fields,
    authorize_nested_leaf_writes,
    find_merged_value_targets,
    find_nested_leaf_targets,
    find_t02_auto_targets,
    nested_authorization_is_current,
)
from core.docx.services.hwpx_xml_scope_diff import XmlScopeTarget, compare_hwpx_xml_scope, sha256_file

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_DATA = Path(__file__).resolve().parents[2] / "data"
_GOLDEN = (
    "(서식09) 연구개발기관 대표의 참여의사 확인서_접수번호(기관명).hwpx",
    "(참여신청서, 개인정보동의서) 서울창업허브 성수, 창동×홈앤쇼핑 오픈이노베이션.hwpx",
    "2025전담PM(자기기술서).hwpx",
    "(첨부3) 성장촉진자금(자동화설비) 신청 자가진단표.hwpx",
    "(별첨1) 2024년도 창업중심대학 예비창업자 사업계획서 양식.hwpx",
    "(붙임2) 신용취약소상공인자금 신청 서식.hwpx",
    "3. SBA 액셀러레이팅 정보 수집 및 이용 동의서 양식(2023년).hwpx",
    "(공고)2024년 2030청년창업프로젝트 초기유형 모집 공고문.hwpx",
    "(필수) 2. 연구개발계획서 본문1.hwpx",
    "2026년도 SaaS 개발환경 지원 수요기업 신청서.hwpx",
)
_CHOICE = frozenset({"해당", "여", "부", "예", "아니오", "확인"})


def _unsafe(label: str) -> bool:
    compact = _compact(label)
    if compact in _CHOICE or _sign_consent_label(compact):
        return True
    return any(mark in label for mark in ("※", "○", "◯", "◦", "●", "□", "■", "☐"))


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _cell(text: str, row: int, col: int, *, col_span: int = 1) -> str:
    body = f"<hp:run><hp:t>{text}</hp:t></hp:run>" if text else "<hp:run></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>"
        + body
        + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + f'<hp:cellSpan rowSpan="1" colSpan="{col_span}"/></hp:tc>'
    )


def _section(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'


def _hwpx(path: Path, section: str) -> None:
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
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))


def _member(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def _leaf_form() -> str:
    inner = "<hp:tbl><hp:tr>" + _cell("속기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr></hp:tbl>"
    outer_value = (
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>바깥유지</hp:t></hp:run>"
        f"{inner}</hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )
    return _section(
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        + _cell("구분", 0, 0)
        + outer_value
        + "</hp:tr><hp:tr>"
        + _cell("기업명", 1, 0)
        + _cell("", 1, 1)
        + "</hp:tr></hp:tbl></hp:run></hp:p>"
    )


def test_nested_leaf_writes_inner_cell_only(tmp_path: Path) -> None:
    src = tmp_path / "nested.hwpx"
    _hwpx(src, _leaf_form())
    before = src.read_bytes()
    header = _member(src, "Contents/header.xml")
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["기업명"]
    assert find_merged_value_targets(index) == ()
    nested = find_nested_leaf_targets(index)
    assert [item.field_label for item in nested] == ["속기업명"]
    assert index.tables[nested[0].table_index].parent_table_index is not None
    grants = authorize_nested_leaf_writes(index)
    assert [item.field_label for item in grants] == ["속기업명"]
    assert nested_authorization_is_current(index, grants[0]) is True
    assert nested_authorization_is_current(index, replace(grants[0], table_index=0)) is False
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))

    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"속기업명": "도보네비", "기업명": "겉회사"})
    assert report.ok is True
    texts = _texts(dst)
    assert "도보네비" in texts and "겉회사" in texts and "바깥유지" in texts
    assert src.read_bytes() == before
    assert _member(dst, "Contents/header.xml") == header
    diff = compare_hwpx_xml_scope(
        src,
        dst,
        [
            XmlScopeTarget(grants[0].section_member, grants[0].paragraph_index, grants[0].run_index, grants[0].text_node_index),
            XmlScopeTarget(
                find_t02_auto_targets(index)[0].section_member,
                find_t02_auto_targets(index)[0].paragraph_index,
                find_t02_auto_targets(index)[0].run_index,
                find_t02_auto_targets(index)[0].text_node_index,
            ),
        ],
        expected_sha256=sha256_file(src),
    )
    assert diff.ok is True and diff.unexpected_count == 0


def test_nested_counters_write_nothing(tmp_path: Path) -> None:
    wide_inner = "<hp:tbl><hp:tr>" + _cell("속기업명", 0, 0) + _cell("", 0, 1, col_span=2) + "</hp:tr></hp:tbl>"
    existing_inner = "<hp:tbl><hp:tr>" + _cell("속기업명", 0, 0) + _cell("이미있음", 0, 1) + "</hp:tr></hp:tbl>"
    signature_inner = "<hp:tbl><hp:tr>" + _cell("서명", 0, 0) + _cell("", 0, 1) + "</hp:tr></hp:tbl>"
    duplicate = (
        "<hp:tbl><hp:tr>" + _cell("속기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr></hp:tbl>"
        "<hp:tbl><hp:tr>" + _cell("속기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr></hp:tbl>"
    )

    def wrap(inner: str) -> str:
        value = (
            "<hp:tc><hp:subList><hp:p><hp:run>"
            + inner
            + "</hp:run></hp:p></hp:subList>"
            '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
        )
        return _section(
            "<hp:p><hp:run><hp:tbl><hp:tr>"
            + _cell("구분", 0, 0)
            + value
            + "</hp:tr></hp:tbl></hp:run></hp:p>"
        )

    for name, section in {
        "wide.hwpx": wrap(wide_inner),
        "existing.hwpx": wrap(existing_inner),
        "signature.hwpx": wrap(signature_inner),
        "duplicate.hwpx": wrap(duplicate),
    }.items():
        src = tmp_path / name
        _hwpx(src, section)
        before = src.read_bytes()
        assert find_nested_leaf_targets(index_hwpx_structure(src)) == ()
        dst = tmp_path / f"out-{name}"
        report = commit_t02_label_writes(src, dst, {"속기업명": "도보네비", "서명": "인"})
        assert report.ok is False and not dst.exists()
        assert src.read_bytes() == before


def test_same_label_in_outer_table_blocks_the_nested_copy(tmp_path: Path) -> None:
    inner = "<hp:tbl><hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr></hp:tbl>"
    value = (
        "<hp:tc><hp:subList><hp:p><hp:run>"
        + inner
        + "</hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )
    section = _section(
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        + _cell("기업명", 1, 0)
        + _cell("", 1, 1)
        + "</hp:tr><hp:tr>"
        + _cell("구분", 0, 0)
        + value
        + "</hp:tr></hp:tbl></hp:run></hp:p>"
    )
    src = tmp_path / "clash.hwpx"
    _hwpx(src, section)
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["기업명"]
    assert find_nested_leaf_targets(index) == ()
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "겉회사"})
    assert report.ok is True
    texts = _texts(dst)
    assert texts.count("겉회사") == 1
    assert "구분" in texts


def test_submit_writes_nested_leaf(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _hwpx(src, _leaf_form())
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"속기업명": "도보네비", "기업명": "겉회사"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    texts = _texts(Path(report.final))
    assert "도보네비" in texts and "겉회사" in texts and "바깥유지" in texts
    assert src.read_bytes() == before
    assert all(
        field.decision != "AUTO" and field.auto_write_allowed is False
        for field in assess_fields(index_hwpx_structure(Path(report.final)))
    )


def test_real_hwpx_nested_qualification(tmp_path: Path) -> None:
    present = [name for name in _GOLDEN if (_DATA / name).is_file()]
    assert len(present) == 10
    chosen: tuple[Path, str] | None = None
    golden_seen = 0
    for path in [(_DATA / name) for name in present] + sorted(_DATA.glob("*.hwpx")):
        if not path.is_file():
            continue
        before = path.read_bytes()
        index = index_hwpx_structure(path)
        targets = find_nested_leaf_targets(index)
        assert path.read_bytes() == before
        if path.name in set(present):
            fields = assess_fields(index)
            assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)
            golden_seen += 1
        for target in targets:
            assert target.row_span == 1 and target.col_span == 1 and target.expected_raw_text == ""
            assert index.tables[target.table_index].parent_table_index is not None
            assert _unsafe(target.field_label) is False
        if chosen is None and targets:
            chosen = (path, targets[0].field_label)
        if golden_seen >= 10 and chosen is not None:
            break
    assert chosen is not None
    source, label = chosen
    before = source.read_bytes()
    sample = tmp_path / "sample.hwpx"
    shutil.copyfile(source, sample)
    assert source.read_bytes() == before
    index = index_hwpx_structure(sample)
    grant = next(item for item in authorize_nested_leaf_writes(index) if item.field_label == label)
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: "중첩자격확인"})
    assert report.ok is True
    assert sample.read_bytes() == source.read_bytes() == before
    assert "중첩자격확인" in _texts(dst)
    diff = compare_hwpx_xml_scope(
        sample,
        dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0
