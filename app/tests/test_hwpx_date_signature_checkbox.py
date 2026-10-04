# -*- coding: utf-8 -*-
"""Gate: date, signature, and checkbox cells.

Signature and handwritten picture cells are not written without a T02 grant.
A checkbox toggles only the matched mark run. A split date scaffold is left
as-is (#201) and stays in residual. Ambiguous dates stay REVIEW_REQUIRED or
AUTHORIZATION_PENDING and are not AUTO.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import commit_t02_label_writes, fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    authorize_t02_writes,
    find_t02_auto_targets,
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


def _hwpx(path: Path, sections: list[str]) -> None:
    header = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="3">'
        '<hh:charPr id="0" textColor="000000"/>'
        '<hh:charPr id="2" textColor="000000"/>'
        '<hh:charPr id="5" textColor="000000"/>'
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


def _sec(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _runs(path: Path) -> list[tuple[str, list[str]]]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    found = []
    for run in root.iter(f"{{{_HP}}}run"):
        if any(etree.QName(child).localname == "tbl" for child in run):
            continue
        texts = [node.text or "" for node in run if etree.QName(node).localname == "t"]
        found.append((run.get("charPrIDRef") or "", texts))
    return found


def _pics(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return sum(1 for _ in root.iter(f"{{{_HP}}}pic"))


def _fill(tmp_path: Path, name: str, body: str, identity: dict[str, str]):
    src = tmp_path / f"{name}.hwpx"
    out = tmp_path / f"{name}-out.hwpx"
    _hwpx(src, [_sec(body)])
    before = src.read_bytes()
    report = fill_hwpx(src, out, identity=identity)
    assert src.read_bytes() == before
    return src, out, report


def _no_auto(path: Path, label: str | None = None) -> None:
    index = index_hwpx_structure(path)
    if label is None:
        assert find_t02_auto_targets(index) == ()
        assert authorize_t02_writes(index) == ()
    else:
        assert all(item.field_label != label for item in find_t02_auto_targets(index))
        assert all(item.field_label != label for item in authorize_t02_writes(index))
    assert all(
        field.decision != "AUTO" and field.auto_write_allowed is False
        for field in assess_fields(index)
    )


def test_signature_label_is_not_written_without_grant(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>서명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="5"><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "sig", body, {"기업명": "도보네비", "서명": "홍길동"})
    assert _runs(out) == [("2", ["기업명"]), ("0", ["도보네비"]), ("2", ["서명"]), ("5", [""])]
    assert report.filled == {"기업명": "도보네비"}
    assert "서명" in report.residual
    assert "[signature] 서명 row=1 col=1 UNFILLED" in report.notes
    assert "홍길동" not in "".join(text for _ref, texts in _runs(out) for text in texts)
    _no_auto(src, "서명")
    refused = tmp_path / "refused.hwpx"
    commit = commit_t02_label_writes(src, refused, {"서명": "홍길동"})
    assert commit.ok is False
    assert not refused.exists()


def test_inline_signature_blank_is_not_replaced(tmp_path: Path) -> None:
    body = """<hp:p><hp:run charPrIDRef="0"><hp:t>서명 : ______</hp:t></hp:run></hp:p>
<hp:p><hp:run charPrIDRef="0"><hp:t>날인 : ______</hp:t></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "sig-line", body, {"서명": "홍길동", "날인": "김철수"})
    assert _runs(out) == _runs(src)
    assert report.filled == {}
    assert "서명" in report.residual and "날인" in report.residual
    assert "[signature] 서명 UNFILLED" in report.notes
    assert "[signature] 날인 UNFILLED" in report.notes
    _no_auto(src)


def test_name_blank_keeps_signature_sibling(tmp_path: Path) -> None:
    body = """<hp:p>
<hp:run charPrIDRef="2"><hp:t>성명 : ______</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>  (서명)</hp:t></hp:run>
</hp:p>"""
    _src, out, report = _fill(tmp_path, "name-sig", body, {"성명": "홍길동"})
    assert _runs(out) == [("2", ["성명 : 홍길동"]), ("5", ["  (서명)"])]
    assert report.filled == {"성명": "홍길동"}
    assert not any(note.startswith("[signature]") for note in report.notes)


def test_existing_signature_text_is_not_overwritten(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>성명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="5"><hp:t>홍길동 (서명)</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "hand-text", body, {"성명": "김철수"})
    assert _runs(out) == _runs(src)
    assert report.filled == {}
    assert "성명" in report.residual
    _no_auto(src)


def test_handwritten_picture_is_not_overwritten(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>성명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="0"><hp:pic><hp:img/></hp:pic><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "pic", body, {"성명": "김철수"})
    assert _pics(out) == 1
    assert _runs(out) == [("2", ["성명"]), ("0", [""])]
    assert report.filled == {}
    assert "성명" in report.residual
    assert "[handwritten] 성명 row=0 col=1 UNFILLED" in report.notes
    _no_auto(src)
    from auto_write.services.hwpx_fill import _set_cell_text

    cell = etree.fromstring(
        f'<hp:tc xmlns:hp="{_HP}"><hp:subList><hp:p>'
        '<hp:run charPrIDRef="0"><hp:pic/><hp:t></hp:t></hp:run>'
        "</hp:p></hp:subList></hp:tc>"
    )
    assert _set_cell_text(cell, "김철수") is False
    assert (cell.find(f".//{{{_HP}}}t").text or "") == ""


def test_underline_shape_still_fills(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="0"><hp:line/><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    _src, out, report = _fill(tmp_path, "line", body, {"기업명": "도보네비"})
    assert report.filled == {"기업명": "도보네비"}
    assert ("0", ["도보네비"]) in _runs(out)


def test_department_and_concurrent_labels_still_fill(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>부서명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>겸직인력</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "dept", body, {"부서명": "전략팀", "겸직인력": "1"})
    joined = "".join(text for _ref, texts in _runs(out) for text in texts)
    assert report.filled == {"부서명": "전략팀", "겸직인력": "1"}
    assert "전략팀" in joined and "1" in joined
    assert not any(note.startswith("[signature]") for note in report.notes)
    index = index_hwpx_structure(src)
    assert {item.field_label for item in authorize_t02_writes(index)} == {"부서명", "겸직인력"}


def test_name_hint_and_seal_certificate_still_fill(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>성명 (서명)</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>인감증명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    _src, out, report = _fill(
        tmp_path, "hint", body, {"성명": "홍길동", "인감증명": "1234"},
    )
    joined = "".join(text for _ref, texts in _runs(out) for text in texts)
    assert report.filled == {"성명": "홍길동", "인감증명": "1234"}
    assert "홍길동" in joined and "1234" in joined
    assert not any(note.startswith("[signature]") for note in report.notes)


def test_representative_beside_seal_label_still_fills(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>대표자</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>서명 (인)</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="2"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "rep", body, {"대표자": "홍길동"})
    joined = "".join(text for _ref, texts in _runs(out) for text in texts)
    assert "홍길동" in joined
    assert joined.count("(인)") == 1
    assert report.filled == {"대표자": "홍길동"}
    _no_auto(src, "서명")


def test_submit_holds_signature_and_writes_company(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>직인</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src = tmp_path / "submit-sig.hwpx"
    out = tmp_path / "submit-sig-out.hwpx"
    _hwpx(src, [_sec(body)])
    report = submit_hwpx(
        src, out, identity={"기업명": "도보네비", "직인": "홍길동"},
        normalize_colors=False, submission_cleanup=False,
    )
    final = Path(report.final)
    joined = "".join(text for _ref, texts in _runs(final) for text in texts)
    assert "도보네비" in joined
    assert "홍길동" not in joined
    assert "직인" in report.residual
    assert "[signature] 직인 row=1 col=1 UNFILLED" in report.notes
    assert not any("직인" in note and note.endswith("GRANT_WRITTEN") for note in report.notes)
    _no_auto(final, "직인")


def test_checkbox_same_run_toggles_only_the_mark(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>사업자형태</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>□개인 □법인</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    _src, out, report = _fill(tmp_path, "chk-same", body, {"사업자형태": "법인"})
    assert _runs(out) == [("2", ["사업자형태"]), ("0", ["□개인 ■법인"])]
    assert report.filled == {"사업자형태": "법인"}
    assert not any(note.startswith("[span]") for note in report.notes)


def test_checkbox_split_option_keeps_sibling_spans(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>사업자형태</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>□</hp:t><hp:t>개</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>인 </hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>□</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>법인</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    _src, out, report = _fill(tmp_path, "chk-split", body, {"사업자형태": "개인"})
    assert _runs(out) == [
        ("2", ["사업자형태"]),
        ("0", ["■", "개"]),
        ("5", ["인 "]),
        ("0", ["□"]),
        ("5", ["법인"]),
    ]
    assert report.filled == {"사업자형태": "개인"}


def test_checkbox_ambiguous_does_not_toggle(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>구분</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>□예</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t> □예</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "chk-amb", body, {"구분": "예"})
    assert _runs(out) == _runs(src)
    assert report.filled == {}
    assert "구분" in report.residual
    assert "■" not in "".join(text for _ref, texts in _runs(out) for text in texts)
    _no_auto(src)


def test_checkbox_split_bracket_is_not_wiped(tmp_path: Path) -> None:
    body = """<hp:p>
<hp:run charPrIDRef="0"><hp:t>동의여부 [ </hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>] 동의</hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t> [ ] 비동의</hp:t></hp:run>
</hp:p>"""
    src = tmp_path / "bracket.hwpx"
    out = tmp_path / "bracket-out.hwpx"
    _hwpx(src, [_sec(body)])
    report = fill_hwpx(src, out, line_edits=[{"anchor": "동의여부", "check": ["동의"]}])
    assert _runs(out) == _runs(src)
    assert any("run 경계 분할" in note for note in report.notes)
    assert "[√]" not in "".join(text for _ref, texts in _runs(out) for text in texts)


def test_checkbox_bracket_in_one_run_toggles_only_the_mark(tmp_path: Path) -> None:
    body = """<hp:p>
<hp:run charPrIDRef="2"><hp:t>안내 </hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>[ ] 동의 [ ] 비동의</hp:t></hp:run>
</hp:p>"""
    src = tmp_path / "bracket-one.hwpx"
    out = tmp_path / "bracket-one-out.hwpx"
    _hwpx(src, [_sec(body)])
    report = fill_hwpx(src, out, line_edits=[{"anchor": "안내", "check": ["동의"]}])
    assert _runs(out) == [("2", ["안내 "]), ("0", ["[√] 동의 [ ] 비동의"])]
    assert report.line_edits_applied >= 1


def test_date_split_scaffold_stays_unfilled(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>작성일</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>2025년 </hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>월 </hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>일</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(
        tmp_path, "date-split", body, {"기업명": "도보네비", "작성일": "2026년 9월 28일"},
    )
    assert _runs(out) == [
        ("2", ["기업명"]),
        ("0", ["도보네비"]),
        ("2", ["작성일"]),
        ("0", ["2025년 "]),
        ("5", ["월 "]),
        ("0", ["일"]),
    ]
    assert report.filled == {"기업명": "도보네비"}
    assert "작성일" in report.residual
    _no_auto(src, "작성일")
    dates = [
        field for field in assess_fields(index_hwpx_structure(src))
        if "DATE_SCAFFOLD" in field.review_reason
    ]
    assert dates
    assert all(
        field.decision in {"NO_TARGET", "REVIEW_REQUIRED"} and field.auto_write_allowed is False
        for field in dates
    )


def test_date_placeholder_split_uses_span_note(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run charPrIDRef="2"><hp:t>작성일</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p>
<hp:run charPrIDRef="0"><hp:t>0000년 </hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>00월 </hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>00일</hp:t></hp:run>
</hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src, out, report = _fill(tmp_path, "date-ph", body, {"작성일": "2026년 9월 28일"})
    assert _runs(out) == _runs(src)
    assert "작성일" in report.residual
    assert "[span] 작성일 row=0 col=1 UNFILLED" in report.notes
    _no_auto(src, "작성일")


def test_date_inline_split_is_not_corrupted(tmp_path: Path) -> None:
    body = """<hp:p>
<hp:run charPrIDRef="2"><hp:t>작성일 : ____</hp:t></hp:run>
<hp:run charPrIDRef="0"><hp:t>년 ____</hp:t></hp:run>
<hp:run charPrIDRef="5"><hp:t>월 ____일</hp:t></hp:run>
</hp:p>"""
    src, out, report = _fill(tmp_path, "date-inline", body, {"작성일": "2026년 9월 28일"})
    assert _runs(out) == _runs(src)
    assert "작성일" in report.residual
    assert report.filled == {}


def test_duplicate_date_across_tables_stays_pending(tmp_path: Path) -> None:
    def table(row_text: str) -> str:
        return f"""<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>작성일</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>{row_text}</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""

    src = tmp_path / "dates.hwpx"
    out = tmp_path / "dates-out.hwpx"
    _hwpx(src, [_sec(table("") + table(""))])
    index = index_hwpx_structure(src)
    fields = [
        field for field in assess_fields(index)
        if field.field_label == "작성일" and field.field_type == "T02"
    ]
    assert len(fields) == 2
    assert all(
        field.decision == "REVIEW_REQUIRED"
        and field.review_reason == ("AUTHORIZATION_PENDING",)
        and field.auto_write_allowed is False
        and field.eligible is True
        for field in fields
    )
    assert authorize_t02_writes(index) == ()
    report = submit_hwpx(
        src, out, identity={"작성일": "2026-09-28"},
        normalize_colors=False, submission_cleanup=False,
    )
    final = Path(report.final)
    joined = "".join(text for _ref, texts in _runs(final) for text in texts)
    assert "2026-09-28" not in joined
    assert "작성일" in report.residual
    assert any(note == "[t02] 작성일 AUTHORIZATION_PENDING" for note in report.notes)
    assert not any(note.endswith("GRANT_WRITTEN") for note in report.notes)
    output = index_hwpx_structure(final)
    assert authorize_t02_writes(output) == ()
    pending = [
        field for field in assess_fields(output)
        if field.field_label == "작성일" and field.field_type == "T02"
    ]
    assert len(pending) == 2
    assert all(
        field.decision == "REVIEW_REQUIRED"
        and field.review_reason == ("AUTHORIZATION_PENDING",)
        and field.auto_write_allowed is False
        for field in pending
    )
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(output))


def test_same_table_duplicate_date_notes_the_unfilled_row(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>작성일</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>작성일</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="1" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src = tmp_path / "date-rows.hwpx"
    out = tmp_path / "date-rows-out.hwpx"
    _hwpx(src, [_sec(body)])
    assert find_t02_auto_targets(index_hwpx_structure(src)) == ()
    assert authorize_t02_writes(index_hwpx_structure(src)) == ()
    report = submit_hwpx(
        src, out, identity={"작성일": "2026-09-28"},
        normalize_colors=False, submission_cleanup=False,
    )
    final = Path(report.final)
    texts = [text for _ref, parts in _runs(final) for text in parts]
    assert texts.count("2026-09-28") == 1
    assert texts.count("") == 1
    assert "작성일" in report.residual
    assert any(note == "[repeated-row] 작성일 row=1 col=1 UNFILLED" for note in report.notes)
    assert not any(note.endswith("GRANT_WRITTEN") for note in report.notes)
    _no_auto(src)
    output = index_hwpx_structure(final)
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in assess_fields(output))
    assert all(item.field_label != "작성일" or item.row != 1 for item in find_t02_auto_targets(output))


def test_unique_empty_date_is_granted_but_not_marked_auto(tmp_path: Path) -> None:
    body = """<hp:p><hp:run><hp:tbl><hp:tr>
<hp:tc><hp:subList><hp:p><hp:run><hp:t>작성일</hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
<hp:tc><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList>
<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>
</hp:tr></hp:tbl></hp:run></hp:p>"""
    src = tmp_path / "date-one.hwpx"
    out = tmp_path / "date-one-out.hwpx"
    _hwpx(src, [_sec(body)])
    index = index_hwpx_structure(src)
    assert [item.field_label for item in authorize_t02_writes(index)] == ["작성일"]
    pending = next(field for field in assess_fields(index) if field.field_label == "작성일")
    assert pending.decision == "REVIEW_REQUIRED"
    assert pending.review_reason == ("AUTHORIZATION_PENDING",)
    assert pending.auto_write_allowed is False
    report = submit_hwpx(
        src, out, identity={"작성일": "2026-09-28"},
        normalize_colors=False, submission_cleanup=False,
    )
    final = Path(report.final)
    assert "2026-09-28" in "".join(text for _ref, texts in _runs(final) for text in texts)
    assert any(note == "[t02] 작성일 GRANT_WRITTEN" for note in report.notes)
    assert all(
        field.decision != "AUTO" and field.auto_write_allowed is False
        for field in assess_fields(index_hwpx_structure(final))
    )
