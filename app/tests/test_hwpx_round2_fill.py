# -*- coding: utf-8 -*-
"""Round-2 HWPX 채움 회귀.

DIPS 예시 칸, onlab 콜론 문단, hwp_ex 라벨 칸, onlab 창업지원금 표를
최소 HWPX 로 재현한다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_fill import _is_hwpx_example_scaffold, _is_prior_support_table
from core.docx.services.hwpx_protected_regions import find_inline_field_targets

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_P = f"{{{_HP}}}"
_H = f"{{{_HH}}}"


def test_example_scaffold_detector_rejects_real_words() -> None:
    assert _is_hwpx_example_scaffold("OOO")
    assert _is_hwpx_example_scaffold("OOOOO")
    assert _is_hwpx_example_scaffold("000-0000-0000")
    assert _is_hwpx_example_scaffold("0000.00.00")
    assert _is_hwpx_example_scaffold("OO도 OO시·군")
    assert _is_hwpx_example_scaffold("개인사업자 / 법인사업자")
    assert _is_hwpx_example_scaffold("남 / 여")
    assert _is_hwpx_example_scaffold("단독 / 공동 / 각자대표") is True
    assert _is_hwpx_example_scaffold("GOOGLE") is False
    assert _is_hwpx_example_scaffold("직위/직책") is False
    assert _is_hwpx_example_scaffold("123-45-67890") is False
    assert _is_hwpx_example_scaffold("서울특별시 강남구 테헤란로") is False


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _header() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="3">'
        '<hh:charPr id="0" height="1000" textColor="#000000"/>'
        '<hh:charPr id="2" height="1000" textColor="#FF0000"/>'
        '<hh:charPr id="34" height="1000" textColor="#0000FF" italic="1"><hh:italic/></hh:charPr>'
        "</hh:charProperties></hh:refList></hh:head>"
    )


def _write(path: Path, section: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", _header().encode("utf-8"))
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))


def _sec(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _cell(col: int, row: int, runs: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f"<hp:subList><hp:p>{runs}</hp:p></hp:subList></hp:tc>"
    )


def _run(text: str, ref: str = "0") -> str:
    return f'<hp:run charPrIDRef="{ref}"><hp:t>{text}</hp:t></hp:run>'


def _row(row: int, label: str, value: str, value_ref: str = "34") -> str:
    return (
        "<hp:tr>"
        + _cell(0, row, _run(label, "0"))
        + _cell(1, row, _run(value, value_ref))
        + "</hp:tr>"
    )


def _root(path: Path):
    with zipfile.ZipFile(path) as archive:
        return etree.fromstring(archive.read("Contents/section0.xml"))


def _charpr(path: Path) -> dict[str, etree._Element]:
    with zipfile.ZipFile(path) as archive:
        header = etree.fromstring(archive.read("Contents/header.xml"))
    found = {}
    for el in header.iter(f"{_H}charPr"):
        if el.get("id"):
            found[el.get("id")] = el
    return found


def _italic(el) -> bool:
    flag = (el.get("italic") or "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    return any(child.tag == f"{_H}italic" for child in el)


def _style(path: Path, text: str) -> tuple[str, bool, str]:
    """(textColor, italic, height) of the run whose text is exactly text."""
    styles = _charpr(path)
    root = _root(path)
    hits = []
    for run in root.iter(f"{_P}run"):
        for node in run:
            if node.tag == f"{_P}t" and (node.text or "") == text:
                el = styles[run.get("charPrIDRef")]
                hits.append((el.get("textColor"), _italic(el), el.get("height")))
    assert len(hits) == 1, text
    return hits[0]


def _tables(path: Path) -> list[list[list[str]]]:
    tables = []
    for tbl in _root(path).iter(f"{_P}tbl"):
        rows = []
        for tr in tbl:
            if tr.tag != f"{_P}tr":
                continue
            rows.append([
                "".join(node.text or "" for node in tc.iter(f"{_P}t"))
                for tc in tr
                if tc.tag == f"{_P}tc"
            ])
        tables.append(rows)
    return tables


def test_example_cells_are_replaced_in_body_style(tmp_path: Path) -> None:
    rows = "".join([
        _row(0, "대표자 성명", "OOO"),
        _row(1, "연락처", "000-0000-0000"),
        _row(2, "기업명", "OOOOO"),
        _row(3, "사업장 소재지", "OO도 OO시·군"),
        _row(4, "개업연월일", "0000.00.00"),
        _row(5, "사업자 구분", "개인사업자 / 법인사업자"),
        _row(6, "이메일", ""),
    ])
    section = _sec(
        '<hp:p><hp:run charPrIDRef="2"><hp:t>빨간안내</hp:t></hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="7" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p>"
    )
    src = tmp_path / "dips.hwpx"
    _write(src, section)
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src,
        out,
        identity={
            "대표자": "홍길동",
            "연락처": "010-1234-5678",
            "기업명": "테스트주식회사",
            "주소": "서울특별시 테스트구 테스트로 123",
            "설립일": "2020-01-15",
            "사업자구분": "법인",
            "이메일": "test@example.com",
        },
        force_black=False,
    )
    assert report.filled["대표자"] == "홍길동"
    assert report.filled["연락처"] == "010-1234-5678"
    assert report.filled["기업명"] == "테스트주식회사"
    assert report.filled["주소"] == "서울특별시 테스트구 테스트로 123"
    assert report.filled["설립일"] == "2020-01-15"
    assert report.filled["사업자구분"] == "법인"
    assert report.filled["이메일"] == "test@example.com"
    xml = zipfile.ZipFile(out).read("Contents/section0.xml").decode("utf-8")
    for leftover in ("OOO", "OOOOO", "000-0000-0000", "OO도 OO시·군", "0000.00.00", "개인사업자 / 법인사업자"):
        assert leftover not in xml
    for value in (
        "홍길동",
        "010-1234-5678",
        "테스트주식회사",
        "서울특별시 테스트구 테스트로 123",
        "2020-01-15",
        "법인",
        "test@example.com",
    ):
        color, italic, height = _style(out, value)
        assert color == "#000000"
        assert italic is False
        assert height == "1000"
    original = _charpr(out)["34"]
    assert original.get("textColor") == "#0000FF"
    assert _italic(original) is True
    assert _style(out, "빨간안내")[0] == "#FF0000"
    assert _style(out, "대표자 성명")[0] == "#000000"


def test_prior_support_table_does_not_take_applicant_identity(tmp_path: Path) -> None:
    prior = (
        "<hp:tr>" + _cell(0, 0, _run("단체명")) + _cell(1, 0, _run("", "0")) + "</hp:tr>"
        "<hp:tr>" + _cell(0, 1, _run("대표자")) + _cell(1, 1, _run("", "0")) + "</hp:tr>"
        "<hp:tr>" + _cell(0, 2, _run("사업명")) + _cell(1, 2, _run("", "0")) + "</hp:tr>"
    )
    applicant = (
        "<hp:tr>" + _cell(0, 0, _run("팀명")) + _cell(1, 0, _run("", "0")) + "</hp:tr>"
        "<hp:tr>" + _cell(0, 1, _run("대표자명")) + _cell(1, 1, _run("", "0")) + "</hp:tr>"
    )
    section = _sec(
        f'<hp:p>{_run("2. 창업지원금")}</hp:p>'
        f'<hp:p>{_run("")}<hp:run charPrIDRef="0"><hp:tbl rowCnt="3" colCnt="2">{prior}</hp:tbl></hp:run></hp:p>'
        f'<hp:p>{_run("1. 신청 개요")}</hp:p>'
        f'<hp:p>{_run("")}<hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="2">{applicant}</hp:tbl></hp:run></hp:p>'
    )
    src = tmp_path / "onlab.hwpx"
    _write(src, section)
    out = tmp_path / "out.hwpx"
    fill_hwpx(
        src,
        out,
        identity={
            "기업명": "테스트주식회사",
            "팀명": "테스트팀",
            "대표자": "홍길동",
            "사업명": "테스트사업",
        },
        force_black=False,
    )
    prior_rows, applicant_rows = _tables(out)
    assert prior_rows[0] == ["단체명", ""]
    assert prior_rows[1] == ["대표자", ""]
    assert prior_rows[2] == ["사업명", "테스트사업"]
    assert applicant_rows[0] == ["팀명", "테스트팀"]
    assert applicant_rows[1] == ["대표자명", "홍길동"]
    assert "테스트주식회사" not in zipfile.ZipFile(out).read("Contents/section0.xml").decode("utf-8")


def test_dips_prior_support_history_does_not_put_current_project_in_support_agency(
    tmp_path: Path,
) -> None:
    history = (
        "<hp:tr>"
        + _cell(0, 0, _run("순번"))
        + _cell(1, 0, _run("사업명"))
        + _cell(2, 0, _run("지원기관"))
        + "</hp:tr>"
        "<hp:tr>"
        + _cell(0, 1, _run("1"))
        + _cell(1, 1, _run("사업명"))
        + _cell(2, 1, _run("OOOOO", "34"))
        + "</hp:tr>"
    )
    section = _sec(
        f'<hp:p>{_run("2. 타 창업지원사업 신청·수행 여부")}</hp:p>'
        f'<hp:p>{_run("")}<hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="3">'
        f"{history}</hp:tbl></hp:run></hp:p>"
    )
    src = tmp_path / "dips_history.hwpx"
    _write(src, section)

    table = next(_root(src).iter(f"{_P}tbl"))
    assert _is_prior_support_table(table) is True

    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src,
        out,
        identity={
            "사업명": "AI 기반 문서 자동작성 플랫폼 고도화",
            "과제명": "현재 신청 과제",
        },
        force_black=False,
    )

    rows = _tables(out)[0]
    assert rows[0] == ["순번", "사업명", "지원기관"]
    assert rows[1] == ["1", "사업명", "OOOOO"]
    xml = zipfile.ZipFile(out).read("Contents/section0.xml").decode("utf-8")
    assert "AI 기반 문서 자동작성 플랫폼 고도화" not in xml
    assert "현재 신청 과제" not in xml
    assert report.filled == {}


def test_inline_colon_keeps_spacing_and_drops_only_edited_lineseg(tmp_path: Path) -> None:
    section = _sec(
        '<hp:p><hp:run charPrIDRef="0"><hp:t>팀      명 :</hp:t></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="3"/></hp:linesegarray></hp:p>'
        '<hp:p><hp:run charPrIDRef="0"><hp:t>대 표 자 :</hp:t></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="4"/></hp:linesegarray></hp:p>'
        '<hp:p><hp:run charPrIDRef="0"><hp:t>이 문장은 고치지 않는다.</hp:t></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="9"/></hp:linesegarray></hp:p>'
    )
    src = tmp_path / "colon.hwpx"
    _write(src, section)
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"팀명": "테스트팀", "대표자": "홍길동"},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )
    final = Path(report.final)
    xml = zipfile.ZipFile(final).read("Contents/section0.xml").decode("utf-8")
    assert "팀      명 : 테스트팀" in xml
    assert "대 표 자 : 홍길동" in xml
    assert 'vertpos="3"' not in xml
    assert 'vertpos="4"' not in xml
    assert 'vertpos="9"' in xml
    assert xml.count("<hp:linesegarray") == 1
    assert "_DRAFT" not in final.name


def test_l074_keeps_untouched_title_lineseg_byte_identical(tmp_path: Path) -> None:
    section = _sec(
        '<hp:p><hp:run charPrIDRef="0"><hp:t>2. 수정하지 않는 제목</hp:t></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="77"/></hp:linesegarray></hp:p>'
        '<hp:p><hp:run charPrIDRef="0"><hp:t>BODY_TOKEN</hp:t></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="88"/></hp:linesegarray></hp:p>'
    )
    src = tmp_path / "l074.hwpx"
    _write(src, section)
    before = _root(src)
    before_title = next(p for p in before.iter(f"{_P}p") if "수정하지 않는 제목" in "".join(t.text or "" for t in p.iter(f"{_P}t")))
    before_lineseg = etree.tostring(next(before_title.iter(f"{_P}linesegarray")))

    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, replacements={"BODY_TOKEN": "수정된 본문"}, force_black=False)

    after = _root(out)
    after_title = next(p for p in after.iter(f"{_P}p") if "수정하지 않는 제목" in "".join(t.text or "" for t in p.iter(f"{_P}t")))
    after_lineseg = etree.tostring(next(after_title.iter(f"{_P}linesegarray")))
    body = next(p for p in after.iter(f"{_P}p") if "수정된 본문" in "".join(t.text or "" for t in p.iter(f"{_P}t")))

    assert after_lineseg == before_lineseg
    assert list(body.iter(f"{_P}linesegarray")) == []

def test_email_stays_out_of_the_label_cell(tmp_path: Path) -> None:
    label = (
        '<hp:run charPrIDRef="34"><hp:t>이 메 일</hp:t></hp:run>'
        '<hp:run charPrIDRef="34"><hp:t></hp:t></hp:run>'
    )
    value = '<hp:run charPrIDRef="34"><hp:t>OOOO</hp:t></hp:run>'
    section = _sec(
        '<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        + _cell(0, 0, label)
        + _cell(1, 0, value)
        + "</hp:tr></hp:tbl></hp:run></hp:p>"
    )
    src = tmp_path / "mail.hwpx"
    _write(src, section)
    index = index_hwpx_structure(src)
    assert index.analysis_status == "COMPLETE"
    assert "이메일" not in [item.field_label for item in find_inline_field_targets(index)]
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src,
        out,
        identity={"이메일": "test@example.com"},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )
    final = Path(report.final)
    rows = _tables(final)[0]
    assert rows == [["이 메 일", "test@example.com"]]
    xml = zipfile.ZipFile(final).read("Contents/section0.xml").decode("utf-8")
    assert xml.count("test@example.com") == 1
    assert "이 메 일test@example.com" not in xml
    assert "OOOO" not in xml
    color, italic, _height = _style(final, "test@example.com")
    assert color == "#000000"
    assert italic is False
    assert _style(final, "이 메 일")[0] == "#0000FF"
    assert "_DRAFT" not in final.name
