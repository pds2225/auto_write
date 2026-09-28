# -*- coding: utf-8 -*-
"""Same-run and same-cell fields keep the label text and fill only the blank."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorize_inline_field_writes,
    find_inline_field_targets,
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


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
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


def _sec(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def test_same_run_appends_after_the_label(tmp_path: Path) -> None:
    section = _sec('<hp:p><hp:run><hp:t>기업명 : </hp:t></hp:run></hp:p>')
    src = tmp_path / "same-run.hwpx"
    _hwpx(src, section)
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_inline_field_targets(index)] == ["기업명"]
    assert find_t02_auto_targets(index) == ()
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "도보네비"})
    assert report.ok is True
    assert _texts(dst) == ["기업명 : 도보네비"]
    assert src.read_bytes() == before
    grant = authorize_inline_field_writes(index)[0]
    diff = compare_hwpx_xml_scope(
        src, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(src),
    )
    assert diff.ok is True and diff.unexpected_count == 0


def test_same_cell_writes_the_empty_run_only(tmp_path: Path) -> None:
    section = _sec(
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        '<hp:tc><hp:subList><hp:p><hp:run><hp:t>주소</hp:t></hp:run><hp:run></hp:run></hp:p></hp:subList>'
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="2"/></hp:tc>'
        "</hp:tr></hp:tbl></hp:run></hp:p>"
    )
    src = tmp_path / "same-cell.hwpx"
    _hwpx(src, section)
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_inline_field_targets(index)] == ["주소"]
    dst = tmp_path / "out.hwpx"
    assert commit_t02_label_writes(src, dst, {"주소": "서울"}).ok is True
    assert _texts(dst) == ["주소", "서울"]


def test_inline_counters_keep_the_label(tmp_path: Path) -> None:
    cases = {
        "seal.hwpx": _sec("<hp:p><hp:run><hp:t>성명 : (서명)</hp:t></hp:run></hp:p>"),
        "filled.hwpx": _sec("<hp:p><hp:run><hp:t>기업명 : 서울</hp:t></hp:run></hp:p>"),
        "guide.hwpx": _sec("<hp:p><hp:run><hp:t>※ 기업명 :</hp:t></hp:run></hp:p>"),
    }
    for name, section in cases.items():
        src = tmp_path / name
        _hwpx(src, section)
        before = src.read_bytes()
        assert find_inline_field_targets(index_hwpx_structure(src)) == ()
        dst = tmp_path / f"out-{name}"
        assert commit_t02_label_writes(src, dst, {"성명": "홍", "기업명": "도보네비"}).ok is False
        assert not dst.exists() and src.read_bytes() == before


def test_real_hwpx_inline_qualification(tmp_path: Path) -> None:
    present = [name for name in _GOLDEN if (_DATA / name).is_file()]
    assert len(present) == 10
    chosen: tuple[Path, str] | None = None
    golden_seen = 0
    for path in [(_DATA / name) for name in present] + sorted(_DATA.glob("*.hwpx")):
        if not path.is_file():
            continue
        before = path.read_bytes()
        index = index_hwpx_structure(path)
        targets = find_inline_field_targets(index)
        assert path.read_bytes() == before
        if path.name in set(present):
            assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
            golden_seen += 1
        for target in targets:
            assert "(서명)" not in target.expected_raw_text and "※" not in target.field_label
        if chosen is None and targets:
            chosen = (path, targets[0].field_label)
        if golden_seen >= 10 and chosen is not None:
            break
    assert chosen is not None
    source, label = chosen
    before = source.read_bytes()
    sample = tmp_path / "sample.hwpx"
    shutil.copyfile(source, sample)
    grant = next(item for item in authorize_inline_field_writes(index_hwpx_structure(sample)) if item.field_label == label)
    prefix = grant.expected_raw_text
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: "인라인확인"})
    assert report.ok is True
    assert sample.read_bytes() == source.read_bytes() == before
    texts = _texts(dst)
    assert any("인라인확인" in text for text in texts)
    if prefix:
        assert any(text.startswith(prefix) for text in texts)
    diff = compare_hwpx_xml_scope(
        sample, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0
