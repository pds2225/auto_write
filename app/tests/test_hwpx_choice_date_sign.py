# -*- coding: utf-8 -*-
"""Checkbox marks can flip. Date scaffolds and signature lines cannot."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorize_checkbox_writes,
    find_checkbox_targets,
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


def _line(text: str) -> str:
    return _sec(f"<hp:p><hp:run><hp:t>{text}</hp:t></hp:run></hp:p>")


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def test_checkbox_flips_only_the_box(tmp_path: Path) -> None:
    src = tmp_path / "box.hwpx"
    _hwpx(src, _line("□예"))
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    assert [item.field_label for item in find_checkbox_targets(index)] == ["예"]
    assert find_t02_auto_targets(index) == ()
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
    dst = tmp_path / "out.hwpx"
    assert commit_t02_label_writes(src, dst, {"예": "예"}).ok is True
    assert _texts(dst) == ["■예"]
    assert src.read_bytes() == before
    grant = authorize_checkbox_writes(index)[0]
    diff = compare_hwpx_xml_scope(
        src, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(src),
    )
    assert diff.ok is True and diff.unexpected_count == 0
    wrong = tmp_path / "wrong.hwpx"
    assert commit_t02_label_writes(src, wrong, {"예": "아니오"}).ok is False
    assert not wrong.exists()


def test_date_signature_and_duplicate_boxes_are_not_grants(tmp_path: Path) -> None:
    cases = {
        "date.hwpx": _line("2024년 월 일"),
        "sign.hwpx": _line("성명 : (서명)"),
        "dup.hwpx": _sec(
            "<hp:p><hp:run><hp:t>□예</hp:t></hp:run></hp:p>"
            "<hp:p><hp:run><hp:t>□예</hp:t></hp:run></hp:p>"
        ),
    }
    for name, section in cases.items():
        src = tmp_path / name
        _hwpx(src, section)
        before = src.read_bytes()
        assert find_checkbox_targets(index_hwpx_structure(src)) == ()
        dst = tmp_path / f"out-{name}"
        assert commit_t02_label_writes(src, dst, {"예": "예", "성명": "홍", "2024년": "3"}).ok is False
        assert not dst.exists() and src.read_bytes() == before


def test_real_hwpx_choice_date_sign_qualification(tmp_path: Path) -> None:
    present = [name for name in _GOLDEN if (_DATA / name).is_file()]
    assert len(present) == 10
    chosen: tuple[Path, str] | None = None
    seen = 0
    paths = [(_DATA / name) for name in present]
    paths.extend(list(sorted(_DATA.glob("*.hwpx")))[:40])
    for path in paths:
        if not path.is_file():
            continue
        before = path.read_bytes()
        index = index_hwpx_structure(path)
        targets = find_checkbox_targets(index)
        assert path.read_bytes() == before
        if path.name in set(present):
            assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
            seen += 1
        for target in targets:
            assert target.expected_raw_text.strip()[:1] in "□☐"
            assert "서명" not in target.expected_raw_text
            assert "년" not in target.field_label
        if chosen is None and targets:
            chosen = (path, targets[0].field_label)
        if seen >= 10 and chosen is not None:
            break
    assert chosen is not None
    source, label = chosen
    before = source.read_bytes()
    sample = tmp_path / "sample.hwpx"
    shutil.copyfile(source, sample)
    grant = next(item for item in authorize_checkbox_writes(index_hwpx_structure(sample)) if item.field_label == label)
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: label})
    assert report.ok is True
    assert sample.read_bytes() == source.read_bytes() == before
    assert any(text.startswith("■") for text in _texts(dst))
    diff = compare_hwpx_xml_scope(
        sample, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0
