# -*- coding: utf-8 -*-
"""Merged value cells: one empty run across columns, still not AUTO."""

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
    authorize_merged_value_writes,
    authorize_t02_writes,
    find_merged_value_targets,
    find_t02_auto_targets,
    merged_authorization_is_current,
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


def _unsafe_merged_label(label: str) -> bool:
    compact = _compact(label)
    if compact in _CHOICE or _sign_consent_label(compact):
        return True
    return any(mark in label for mark in ("※", "○", "◯", "◦", "●", "□", "■", "☐"))


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


def _cell(
    text: str,
    row: int,
    col: int,
    *,
    col_span: int = 1,
    row_span: int = 1,
    runs: int = 1,
) -> str:
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
        + f'<hp:cellSpan rowSpan="{row_span}" colSpan="{col_span}"/></hp:tc>'
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


def _member(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        roots = [
            etree.fromstring(archive.read(name))
            for name in archive.namelist()
            if name.startswith("Contents/section")
        ]
    return [node.text or "" for root in roots for node in root.iter(f"{{{_HP}}}t")]


def _spans(path: Path) -> list[tuple[str | None, str | None]]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    found = []
    for node in root.iter(f"{{{_HP}}}cellSpan"):
        found.append((node.get("rowSpan"), node.get("colSpan")))
    return found


def _simple_merge() -> str:
    return _section(_table([
        [_cell("주소", 0, 0), _cell("", 0, 1, col_span=3)],
        [_cell("기업명", 1, 0), _cell("", 1, 1)],
    ]))


def test_horizontal_merge_writes_only_the_empty_run(tmp_path: Path) -> None:
    src = tmp_path / "merge.hwpx"
    _hwpx(src, [_simple_merge()])
    before = src.read_bytes()
    header = _member(src, "Contents/header.xml")
    spans_before = _spans(src)
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["기업명"]
    merged = find_merged_value_targets(index)
    assert [item.field_label for item in merged] == ["주소"]
    assert merged[0].col_span == 3 and merged[0].row_span == 1
    assert authorize_t02_writes(index)[0].field_label == "기업명"
    grants = authorize_merged_value_writes(index)
    assert [item.field_label for item in grants] == ["주소"]
    assert merged_authorization_is_current(index, grants[0]) is True
    assert merged_authorization_is_current(index, replace(grants[0], col_span=1)) is False
    fields = assess_fields(index)
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)
    assert not any(field.field_label == "주소" and field.eligible for field in fields)

    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"주소": "서울시 강남구", "기업명": "도보네비"})
    assert report.ok is True
    assert src.read_bytes() == before
    assert _member(dst, "Contents/header.xml") == header
    assert _spans(dst) == spans_before
    assert _texts(dst)[0] == "주소"
    assert "서울시 강남구" in _texts(dst)
    assert "도보네비" in _texts(dst)
    diff = compare_hwpx_xml_scope(
        src,
        dst,
        [
            XmlScopeTarget(grants[0].section_member, grants[0].paragraph_index, grants[0].run_index, grants[0].text_node_index),
            XmlScopeTarget(
                authorize_t02_writes(index)[0].section_member,
                authorize_t02_writes(index)[0].paragraph_index,
                authorize_t02_writes(index)[0].run_index,
                authorize_t02_writes(index)[0].text_node_index,
            ),
        ],
        expected_sha256=sha256_file(src),
    )
    assert diff.ok is True and diff.unexpected_count == 0


def test_merged_counters_write_nothing(tmp_path: Path) -> None:
    cases = {
        "vertical.hwpx": _section(_table([[
            _cell("대표", 0, 0),
            _cell("", 0, 1, row_span=2),
        ], [
            _cell("총괄", 1, 0),
        ]])),
        "multirun.hwpx": _section(_table([[
            _cell("참고사항", 0, 0),
            _cell("", 0, 1, col_span=4, runs=2),
        ]])),
        "guidance.hwpx": _section(_table([[
            _cell("주소", 0, 0),
            _cell("", 0, 1, col_span=2),
            _cell("※ 작성 후 삭제", 0, 3),
        ]])),
        "existing.hwpx": _section(_table([[
            _cell("주소", 0, 0),
            _cell("서울", 0, 1, col_span=2),
        ]])),
        "nested.hwpx": _section(
            "<hp:p><hp:run><hp:tbl><hp:tr>"
            + _cell("겉라벨", 0, 0)
            + "<hp:tc><hp:subList><hp:p><hp:run><hp:tbl><hp:tr>"
            + _cell("속기업명", 0, 0)
            + _cell("", 0, 1, col_span=2)
            + "</hp:tr></hp:tbl></hp:run></hp:p></hp:subList>"
            + '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
            + "</hp:tr></hp:tbl></hp:run></hp:p>"
        ),
        "signature.hwpx": _section(_table([[
            _cell("서명", 0, 0),
            _cell("", 0, 1, col_span=2),
        ]])),
        "choice.hwpx": _section(_table([[
            _cell("해당", 0, 0),
            _cell("", 0, 1, col_span=2),
        ]])),
        "date.hwpx": _section(_table([[
            _cell("2024년", 0, 0),
            _cell("", 0, 1, col_span=2),
        ]])),
        "repeated.hwpx": _section(_table([
            [_cell("주소", 0, 0), _cell("", 0, 1, col_span=2)],
            [_cell("", 1, 0), _cell("", 1, 1, col_span=2)],
        ])),
    }
    for name, section in cases.items():
        src = tmp_path / name
        _hwpx(src, [section])
        before = src.read_bytes()
        assert find_merged_value_targets(index_hwpx_structure(src)) == ()
        dst = tmp_path / f"out-{name}"
        report = commit_t02_label_writes(src, dst, {"주소": "서울", "참고사항": "메모", "대표": "김", "서명": "인"})
        assert report.ok is False and not dst.exists()
        assert src.read_bytes() == before


def test_duplicate_merged_label_is_not_granted(tmp_path: Path) -> None:
    body = _section(
        _table([[_cell("주소", 0, 0), _cell("", 0, 1, col_span=2)]])
        + _table([[_cell("주소", 0, 0), _cell("", 0, 1, col_span=3)]])
    )
    src = tmp_path / "dup.hwpx"
    _hwpx(src, [body])
    assert find_merged_value_targets(index_hwpx_structure(src)) == ()
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"주소": "서울"})
    assert report.ok is False and not dst.exists()


def test_submit_writes_merged_grant_and_holds_multirun_wide_cell(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _hwpx(src, [
        _simple_merge(),
        _section(_table([[_cell("참고사항", 4, 0), _cell("", 4, 1, col_span=6, runs=2)]])),
    ])
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"주소": "서울시", "기업명": "도보네비", "참고사항": "메모"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    final = Path(report.final)
    texts = _texts(final)
    assert "서울시" in texts and "도보네비" in texts and "메모" not in texts
    assert report.filled["주소"] == "서울시"
    assert "참고사항" in report.residual
    assert any(note == "[t02] 참고사항 AUTHORIZATION_PENDING" for note in report.notes)
    assert src.read_bytes() == before
    output_fields = assess_fields(index_hwpx_structure(final))
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in output_fields)


def test_real_hwpx_merged_qualification(tmp_path: Path) -> None:
    present = [name for name in _GOLDEN if (_DATA / name).is_file()]
    assert len(present) == 10
    sample = tmp_path / "sample.hwpx"
    chosen: tuple[Path, str] | None = None
    for path in [(_DATA / name) for name in present] + sorted(_DATA.glob("*.hwpx")):
        if not path.is_file():
            continue
        before = path.read_bytes()
        index = index_hwpx_structure(path)
        targets = find_merged_value_targets(index)
        assert path.read_bytes() == before
        fields = assess_fields(index)
        assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)
        for target in targets:
            assert target.row_span == 1 and target.col_span is not None and target.col_span > 1
            assert target.expected_raw_text == ""
            assert _unsafe_merged_label(target.field_label) is False
        if chosen is None and targets:
            chosen = (path, targets[0].field_label)
        if chosen is not None and path.name in set(present) and len(present) == 10:
            if all((_DATA / name).is_file() for name in present):
                # Golden files are always fully checked. Stop once a real target exists
                # and the walk has passed every golden name.
                if path.name == present[-1] or chosen[0].name not in set(present):
                    break
    assert chosen is not None
    source, label = chosen
    before = source.read_bytes()
    shutil.copyfile(source, sample)
    assert source.read_bytes() == before
    index = index_hwpx_structure(sample)
    grant = next(item for item in authorize_merged_value_writes(index) if item.field_label == label)
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: "병합자격확인"})
    assert report.ok is True and dst.is_file()
    assert sample.read_bytes() == source.read_bytes() == before
    assert "병합자격확인" in _texts(dst)
    diff = compare_hwpx_xml_scope(
        sample,
        dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0 and diff.out_of_scope_xml_change is False
    written = assess_fields(index_hwpx_structure(dst))
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in written)
