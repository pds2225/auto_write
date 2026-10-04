# -*- coding: utf-8 -*-
"""Guidance narrative cells: fill the trailing empty run and keep the guidance."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorize_guidance_narrative_writes,
    find_guidance_narrative_targets,
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
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def _pair(runs: str) -> str:
    return _section("<hp:tr>" + _label("사업개요") + _value(runs) + "</hp:tr>")


def test_trailing_empty_run_keeps_guidance(tmp_path: Path) -> None:
    src = tmp_path / "guide.hwpx"
    _hwpx(src, _pair("<hp:run><hp:t>※ 개요를 작성</hp:t></hp:run><hp:run></hp:run>"))
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    assert find_t02_auto_targets(index) == ()
    assert [item.field_label for item in find_guidance_narrative_targets(index)] == ["사업개요"]
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"사업개요": "도보 내비게이션"})
    assert report.ok is True
    texts = _texts(dst)
    assert "※ 개요를 작성" in texts and "도보 내비게이션" in texts
    assert src.read_bytes() == before
    grant = authorize_guidance_narrative_writes(index)[0]
    diff = compare_hwpx_xml_scope(
        src, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(src),
    )
    assert diff.ok is True and diff.unexpected_count == 0


def test_guidance_counters_write_nothing(tmp_path: Path) -> None:
    cases = {
        "middle.hwpx": _pair(
            "<hp:run><hp:t>※ 앞</hp:t></hp:run><hp:run></hp:run><hp:run><hp:t>뒤</hp:t></hp:run>"
        ),
        "spacer.hwpx": _pair(
            "<hp:run><hp:t>※ 앞</hp:t></hp:run><hp:run><hp:t> </hp:t></hp:run><hp:run></hp:run>"
        ),
        "signature.hwpx": _pair(
            "<hp:run><hp:t>※ 작성 (서명)</hp:t></hp:run><hp:run></hp:run>"
        ),
        "noguide.hwpx": _pair("<hp:run><hp:t>일반문장</hp:t></hp:run><hp:run></hp:run>"),
    }
    for name, section in cases.items():
        src = tmp_path / name
        _hwpx(src, section)
        before = src.read_bytes()
        assert find_guidance_narrative_targets(index_hwpx_structure(src)) == ()
        dst = tmp_path / f"out-{name}"
        assert commit_t02_label_writes(src, dst, {"사업개요": "값"}).ok is False
        assert not dst.exists() and src.read_bytes() == before


def test_two_guidance_paragraphs_for_one_label_are_refused(tmp_path: Path) -> None:
    runs = "<hp:run><hp:t>※ 첫째</hp:t></hp:run><hp:run></hp:run>"
    value = (
        "<hp:tc><hp:subList><hp:p>" + runs + "</hp:p><hp:p>" + runs + "</hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )
    src = tmp_path / "two.hwpx"
    _hwpx(src, _section("<hp:tr>" + _label("사업개요") + value + "</hp:tr>"))
    assert find_guidance_narrative_targets(index_hwpx_structure(src)) == ()


def test_submit_guidance_narrative(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _hwpx(src, _pair("<hp:run><hp:t>※ 개요를 작성</hp:t></hp:run><hp:run></hp:run>"))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src, out, identity={"사업개요": "도보 내비게이션"},
        normalize_colors=False, submission_cleanup=False,
    )
    texts = _texts(Path(report.final))
    assert "도보 내비게이션" in texts and "※ 개요를 작성" in texts
    assert src.read_bytes() == before


def test_real_hwpx_guidance_narrative_qualification(tmp_path: Path) -> None:
    present = [name for name in _GOLDEN if (_DATA / name).is_file()]
    assert len(present) == 10
    chosen: tuple[Path, str] | None = None
    golden_seen = 0
    for path in [(_DATA / name) for name in present] + sorted(_DATA.glob("*.hwpx")):
        if not path.is_file():
            continue
        before = path.read_bytes()
        index = index_hwpx_structure(path)
        targets = find_guidance_narrative_targets(index)
        assert path.read_bytes() == before
        if path.name in set(present):
            assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(index))
            golden_seen += 1
        for target in targets:
            assert target.expected_raw_text == ""
            assert "※" not in target.field_label
        if chosen is None and targets:
            chosen = (path, targets[0].field_label)
        if golden_seen >= 10 and chosen is not None:
            break
    assert chosen is not None
    source, label = chosen
    before = source.read_bytes()
    sample = tmp_path / "sample.hwpx"
    shutil.copyfile(source, sample)
    grant = next(item for item in authorize_guidance_narrative_writes(index_hwpx_structure(sample)) if item.field_label == label)
    guidance_before = _texts(sample)
    dst = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(sample, dst, {label: "서술칸확인"})
    assert report.ok is True
    assert sample.read_bytes() == source.read_bytes() == before
    after = _texts(dst)
    assert "서술칸확인" in after
    assert all(text in after for text in guidance_before if text)
    diff = compare_hwpx_xml_scope(
        sample, dst,
        [XmlScopeTarget(grant.section_member, grant.paragraph_index, grant.run_index, grant.text_node_index)],
        expected_sha256=sha256_file(sample),
    )
    assert diff.ok is True and diff.unexpected_count == 0
