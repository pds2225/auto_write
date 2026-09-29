# -*- coding: utf-8 -*-
"""Repeated rows: one row key plus a column header names one empty cell."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    _compact,
    _sign_consent_label,
    assess_fields,
    authorize_repeated_row_writes,
    find_repeated_row_targets,
    find_t02_auto_targets,
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


def _unsafe(label: str) -> bool:
    compact = _compact(label)
    if _sign_consent_label(compact):
        return True
    return any(mark in label for mark in ("※", "○", "◯", "□", "■"))


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


def _table(rows: list[list[str]]) -> str:
    return "<hp:p><hp:run><hp:tbl>" + "".join("<hp:tr>" + "".join(row) + "</hp:tr>" for row in rows) + "</hp:tbl></hp:run></hp:p>"


def _section(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'


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
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def _people() -> str:
    return _section(_table([
        [_cell("직원명", 0, 0), _cell("부서", 0, 1)],
        [_cell("홍길동", 1, 0), _cell("", 1, 1)],
        [_cell("김영희", 2, 0), _cell("", 2, 1)],
        [_cell("이철수", 3, 0), _cell("", 3, 1)],
    ]))


def test_repeated_row_writes_only_the_named_cell(tmp_path: Path) -> None:
    src = tmp_path / "rows.hwpx"
    _hwpx(src, _people())
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    assert find_t02_auto_targets(index) == ()
    labels = [item.field_label for item in find_repeated_row_targets(index)]
    assert labels == ["홍길동/부서", "김영희/부서", "이철수/부서"]
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"홍길동/부서": "개발팀"})
    assert report.ok is True
    texts = _texts(dst)
    assert "개발팀" in texts
    assert texts.count("개발팀") == 1
    assert "홍길동" in texts and "김영희" in texts and "부서" in texts
    assert src.read_bytes() == before
    grant = next(item for item in authorize_repeated_row_writes(index) if item.field_label == "홍길동/부서")
    diff = compare_hwpx_xml_scope(
        src,
        dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(src),
    )
    assert diff.ok is True and diff.unexpected_count == 0
    refused = tmp_path / "header.hwpx"
    assert commit_t02_label_writes(src, refused, {"부서": "개발팀"}).ok is False
    assert not refused.exists()


def test_repeated_row_counters(tmp_path: Path) -> None:
    single = _section(_table([
        [_cell("직원명", 0, 0), _cell("부서", 0, 1)],
        [_cell("홍길동", 1, 0), _cell("", 1, 1)],
    ]))
    duplicate = _section(_table([
        [_cell("직원명", 0, 0), _cell("부서", 0, 1)],
        [_cell("홍길동", 1, 0), _cell("", 1, 1)],
        [_cell("홍길동", 2, 0), _cell("", 2, 1)],
        [_cell("김영희", 3, 0), _cell("", 3, 1)],
    ]))
    guidance = _section(_table([
        [_cell("구분", 0, 0), _cell("※ 안내", 0, 1)],
        [_cell("가", 1, 0), _cell("", 1, 1)],
        [_cell("나", 2, 0), _cell("", 2, 1)],
    ]))
    for name, section, forbidden in (
        ("single.hwpx", single, "홍길동/부서"),
        ("guidance.hwpx", guidance, "가/안내"),
    ):
        src = tmp_path / name
        _hwpx(src, section)
        assert find_repeated_row_targets(index_hwpx_structure(src)) == ()
        dst = tmp_path / f"out-{name}"
        assert commit_t02_label_writes(src, dst, {forbidden: "값"}).ok is False
        assert not dst.exists()
    src = tmp_path / "duplicate.hwpx"
    _hwpx(src, duplicate)
    labels = [item.field_label for item in find_repeated_row_targets(index_hwpx_structure(src))]
    assert "홍길동/부서" not in labels
    assert "김영희/부서" in labels


def test_submit_repeated_row_keeps_other_rows(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _hwpx(src, _people())
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src, out, identity={"김영희/부서": "기획팀"},
        normalize_colors=False, submission_cleanup=False,
    )
    texts = _texts(Path(report.final))
    assert "기획팀" in texts and texts.count("기획팀") == 1
    assert "홍길동" in texts and "이철수" in texts
    assert src.read_bytes() == before


def test_real_hwpx_repeated_row_qualification(tmp_path: Path) -> None:
    present = [name for name in _GOLDEN if (_DATA / name).is_file()]
    assert len(present) == 10
    chosen: tuple[Path, str] | None = None
    golden_seen = 0
    for path in [(_DATA / name) for name in present] + sorted(_DATA.glob("*.hwpx")):
        if not path.is_file():
            continue
        before = path.read_bytes()
        index = index_hwpx_structure(path)
        targets = find_repeated_row_targets(index)
        assert path.read_bytes() == before
        if path.name in set(present):
            assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
            golden_seen += 1
        for target in targets:
            assert "/" in target.field_label and target.expected_raw_text == ""
            assert target.row_span == 1 and target.col_span == 1
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
    grant = next(item for item in authorize_repeated_row_writes(index_hwpx_structure(sample)) if item.field_label == label)
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: "반복행확인"})
    assert report.ok is True
    assert sample.read_bytes() == source.read_bytes() == before
    assert _texts(dst).count("반복행확인") == 1
    diff = compare_hwpx_xml_scope(
        sample, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0
