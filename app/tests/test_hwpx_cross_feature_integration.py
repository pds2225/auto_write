# -*- coding: utf-8 -*-
"""Gate: stacked HWPX protections in one document.

One fixture carries merged cells, a nested table, repeated rows, duplicate
labels, guidance, split spans, a date scaffold, signature/seal/handwritten
marks, checkboxes, and pre-filled cells next to empty ones. Writes stay on
the empty value ``hp:t`` that belongs to that label.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_acceptance import run_hwpx_acceptance
from auto_write.services.hwpx_fill import (
    F01_CANONICAL_SHA256,
    ExactTextTarget,
    commit_exact_text_writes,
    commit_t02_label_writes,
    fill_hwpx,
)
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


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" '
        'media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _cell(text: str, row: int, col: int, *, colspan: int = 1, rowspan: int = 1, runs: str | None = None) -> str:
    if runs is None:
        body = f"<hp:run><hp:t>{text}</hp:t></hp:run>" if text else "<hp:run><hp:t></hp:t></hp:run>"
    else:
        body = runs
    return (
        "<hp:tc><hp:subList><hp:p>"
        + body
        + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + f'<hp:cellSpan rowSpan="{rowspan}" colSpan="{colspan}"/></hp:tc>'
    )


def _rows(rows: list[list[str]]) -> str:
    return "".join("<hp:tr>" + "".join(row) + "</hp:tr>" for row in rows)


def _tbl(rows: list[list[str]]) -> str:
    return "<hp:tbl>" + _rows(rows) + "</hp:tbl>"


def _wrapped(inner: str) -> str:
    return "<hp:p><hp:run>" + inner + "</hp:run></hp:p>"


def _nested_value(row: int, col: int, inner_rows: list[list[str]]) -> str:
    return (
        "<hp:tc><hp:subList><hp:p><hp:run>"
        + _tbl(inner_rows)
        + "</hp:run></hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + '<hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _section() -> str:
    sales = (
        '<hp:run charPrIDRef="0"><hp:t>000</hp:t></hp:run>'
        '<hp:run charPrIDRef="5"><hp:t>억원</hp:t></hp:run>'
    )
    dated = (
        '<hp:run charPrIDRef="0"><hp:t>2025년 </hp:t></hp:run>'
        '<hp:run charPrIDRef="5"><hp:t>월 </hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>일</hp:t></hp:run>'
    )
    signed = '<hp:run charPrIDRef="0"><hp:pic><hp:img/></hp:pic><hp:t></hp:t></hp:run>'
    main = [
        [_cell("기업명", 0, 0), _cell("기존회사", 0, 1)],
        [_cell("주소", 1, 0), _cell("", 1, 1)],
        [_cell("매출", 2, 0), _cell("", 2, 1, runs=sales)],
        [_cell("작성일", 3, 0), _cell("", 3, 1, runs=dated)],
        [_cell("서명", 4, 0), _cell("", 4, 1)],
        [_cell("성명", 5, 0), _cell("", 5, 1, runs=signed)],
        [_cell("대표자", 6, 0), _cell("", 6, 1), _cell("서명 (인)", 6, 2)],
        [_cell("사업자형태", 7, 0), _cell("□개인 □법인", 7, 1)],
        [_cell("겉라벨", 8, 0), _nested_value(8, 1, [[_cell("속기업명", 0, 0), _cell("", 0, 1)]])],
        [_cell("연락처", 9, 0), _cell("기존데이터", 9, 2)],
        [_cell("총괄", 10, 0, rowspan=2), _cell("", 10, 1, rowspan=2)],
        [_cell("세부", 11, 2)],
        [_cell("넓은주소", 12, 0), _cell("", 12, 1, colspan=2)],
        [_cell("직원명", 13, 0), _cell("", 13, 1)],
        [_cell("직원명", 14, 0), _cell("", 14, 1)],
        [_cell("매출액", 15, 0), _cell("", 15, 1)],
        [_cell("포함표", 16, 0), _nested_value(16, 1, [[_cell("", 0, 0), _cell("", 0, 1)]])],
    ]
    fax = [[_cell("팩스", 0, 0), _cell("", 0, 1)]]
    guide = (
        '<hp:p>'
        '<hp:run charPrIDRef="2"><hp:t>작성방법:</hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t> 예시를 참고하십시오</hp:t></hp:run>'
        "</hp:p>"
        '<hp:p><hp:run charPrIDRef="0"><hp:t>※ 안내문입니다</hp:t></hp:run></hp:p>'
        '<hp:p>'
        '<hp:run charPrIDRef="2"><hp:t>선택확인 </hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>[ ] 동의 [ ] 비동의</hp:t></hp:run>'
        "</hp:p>"
    )
    body = _wrapped(_tbl(main)) + _wrapped(_tbl(fax)) + _wrapped(_tbl(fax)) + guide
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _hwpx(path: Path) -> str:
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
        archive.writestr("Contents/section0.xml", _section().encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _root(path: Path):
    with zipfile.ZipFile(path) as archive:
        return etree.fromstring(archive.read("Contents/section0.xml"))


def _local(node) -> str:
    return etree.QName(node).localname


def _nearest_cell(node):
    cur = node.getparent()
    while cur is not None:
        if _local(cur) == "tc":
            return cur
        cur = cur.getparent()
    return None


def _cells(path: Path) -> list[dict]:
    root = _root(path)
    found = []
    for table_index, tbl in enumerate(root.iter(f"{{{_HP}}}tbl")):
        for tr in tbl:
            if _local(tr) != "tr":
                continue
            for tc in tr:
                if _local(tc) != "tc":
                    continue
                addr = next((child for child in tc if _local(child) == "cellAddr"), None)
                span = next((child for child in tc if _local(child) == "cellSpan"), None)
                texts = []
                pics = 0
                for node in tc.iter():
                    if _nearest_cell(node) is not tc:
                        continue
                    if _local(node) == "t":
                        texts.append(node.text or "")
                    elif _local(node) == "pic":
                        pics += 1
                nested = any(
                    _local(node) == "tbl" and _nearest_cell(node) is tc
                    for node in tc.iter()
                )
                found.append({
                    "table": table_index,
                    "row": None if addr is None else int(addr.get("rowAddr")),
                    "col": None if addr is None else int(addr.get("colAddr")),
                    "rowspan": None if span is None else int(span.get("rowSpan")),
                    "colspan": None if span is None else int(span.get("colSpan")),
                    "texts": texts,
                    "pics": pics,
                    "nested": nested,
                })
    return found


def _at(cells: list[dict], table: int, row: int, col: int) -> dict:
    return next(cell for cell in cells if cell["table"] == table and cell["row"] == row and cell["col"] == col)


def _body_runs(path: Path) -> list[tuple[str, list[str]]]:
    found = []
    for child in _root(path):
        if _local(child) != "p":
            continue
        for run in child:
            if _local(run) != "run" or any(_local(node) == "tbl" for node in run):
                continue
            texts = [node.text or "" for node in run if _local(node) == "t"]
            found.append((run.get("charPrIDRef") or "", texts))
    return found


def _member(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def _all_texts(path: Path) -> list[str]:
    texts = [text for cell in _cells(path) for text in cell["texts"]]
    texts.extend(text for _ref, parts in _body_runs(path) for text in parts)
    return texts


def _foreign_t(path: Path) -> int:
    count = 0
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.endswith(".xml"):
                continue
            root = etree.fromstring(archive.read(name))
            for node in root.iter():
                qname = etree.QName(node)
                if qname.localname == "t" and qname.namespace != _HP:
                    count += 1
    return count


def _identity() -> dict[str, str]:
    return {
        "기업명": "새회사",
        "주소": "서울",
        "매출": "12",
        "매출액": "99",
        "작성일": "2026년 9월 28일",
        "서명": "홍길동서명",
        "성명": "김철수",
        "대표자": "홍길동",
        "사업자형태": "법인",
        "연락처": "010",
        "겉라벨": "부모값",
        "속기업명": "자식회사",
        "포함표": "들어가면안됨",
        "직원명": "첫번째",
        "팩스": "02",
        "총괄": "침범",
        "넓은주소": "부산",
    }


def _line_edits() -> list[dict]:
    return [{"anchor": "선택확인", "check": ["동의"]}]


def _assert_no_auto(path: Path) -> None:
    fields = assess_fields(index_hwpx_structure(path))
    assert fields
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)


def _assert_structure_held(before: list[dict], after: list[dict], changed: dict[tuple[int, int, int], list[str]]) -> None:
    assert [(cell["table"], cell["row"], cell["col"], cell["rowspan"], cell["colspan"], cell["nested"]) for cell in before] == [
        (cell["table"], cell["row"], cell["col"], cell["rowspan"], cell["colspan"], cell["nested"]) for cell in after
    ]
    for left, right in zip(before, after):
        key = (left["table"], left["row"], left["col"])
        if key in changed:
            assert right["texts"] == changed[key]
        else:
            assert right["texts"] == left["texts"]
        assert right["pics"] == left["pics"]


def test_combined_document_keeps_stacked_protections(tmp_path: Path) -> None:
    src = tmp_path / "combined.hwpx"
    sha = _hwpx(src)
    before_bytes = src.read_bytes()
    header = _member(src, "Contents/header.xml")
    package = _member(src, "Contents/content.hpf")
    before_cells = _cells(src)
    before_runs = _body_runs(src)
    assert _foreign_t(src) == 0
    index = index_hwpx_structure(src)
    assert index.analysis_status == "COMPLETE"
    assert index.tables[0].parent_table_index is None
    assert [table.parent_table_index for table in index.tables].count(0) == 2
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["팩스", "팩스"]
    assert authorize_t02_writes(index) == ()
    _assert_no_auto(src)
    guides = run_hwpx_acceptance(src)
    assert guides.guides == 1
    assert "작성방법" in guides.guides_samples[0]

    out = tmp_path / "filled.hwpx"
    report = fill_hwpx(
        src, out,
        identity=_identity(),
        line_edits=_line_edits(),
        force_black=False,
    )
    filled = _cells(out)
    _assert_structure_held(before_cells, filled, {
        (0, 1, 1): ["서울"],
        (0, 6, 1): ["홍길동"],
        (0, 7, 1): ["□개인 ■법인"],
        (0, 10, 1): ["침범"],
        (0, 12, 1): ["부산"],
        (0, 13, 1): ["첫번째"],
        (0, 15, 1): ["99"],
        (1, 0, 1): ["자식회사"],
        (3, 0, 1): ["02"],
    })
    assert _at(filled, 0, 0, 1)["texts"] == ["기존회사"]
    assert _at(filled, 0, 2, 1)["texts"] == ["000", "억원"]
    assert _at(filled, 0, 3, 1)["texts"] == ["2025년 ", "월 ", "일"]
    assert _at(filled, 0, 4, 1)["texts"] == [""]
    assert _at(filled, 0, 5, 1)["texts"] == [""]
    assert _at(filled, 0, 5, 1)["pics"] == 1
    assert _at(filled, 0, 6, 2)["texts"] == ["서명 (인)"]
    assert _at(filled, 0, 8, 1)["texts"] == []
    assert _at(filled, 0, 8, 1)["nested"] is True
    assert _at(filled, 0, 9, 2)["texts"] == ["기존데이터"]
    assert _at(filled, 0, 10, 1)["rowspan"] == 2
    assert _at(filled, 0, 11, 2)["texts"] == ["세부"]
    assert _at(filled, 0, 14, 1)["texts"] == [""]
    assert _at(filled, 0, 16, 1)["texts"] == []
    assert _at(filled, 2, 0, 0)["texts"] == [""]
    assert _at(filled, 2, 0, 1)["texts"] == [""]
    assert _at(filled, 4, 0, 1)["texts"] == [""]
    assert not any(cell["row"] == 9 and cell["col"] == 1 for cell in filled)
    assert not any(cell["row"] == 11 and cell["col"] == 1 for cell in filled)
    texts = _all_texts(out)
    for leaked in ("새회사", "김철수", "12", "010", "부모값", "들어가면안됨", "2026년 9월 28일", "홍길동서명"):
        assert leaked not in texts
        assert all(leaked not in text for text in texts)
    assert texts.count("첫번째") == 1
    assert texts.count("자식회사") == 1
    assert texts.count("침범") == 1
    runs = _body_runs(out)
    assert runs[:4] == before_runs[:4]
    assert runs[4] == ("0", ["[√] 동의 [ ] 비동의"])
    assert report.line_edits_applied >= 1
    assert report.filled["주소"] == "서울"
    assert report.filled["대표자"] == "홍길동"
    assert report.filled["매출액"] == "99"
    assert report.filled["속기업명"] == "자식회사"
    assert "성명" not in report.filled
    assert "매출" not in report.filled
    assert "겉라벨" not in report.filled
    assert "포함표" not in report.filled
    assert "[existing] 기업명 row=0 col=1 EXISTING_VALUE" in report.notes
    assert "[span] 매출 row=2 col=1 UNFILLED" in report.notes
    assert "[signature] 서명 row=4 col=1 UNFILLED" in report.notes
    assert "[handwritten] 성명 row=5 col=1 UNFILLED" in report.notes
    assert "[nested] 겉라벨 row=8 col=1 UNFILLED" in report.notes
    assert "[nested] 포함표 row=16 col=1 UNFILLED" in report.notes
    assert not any("겉라벨" in note and "EXISTING_VALUE" in note for note in report.notes)
    assert not any(note.endswith("GRANT_WRITTEN") for note in report.notes)
    assert _member(out, "Contents/header.xml") == header
    assert _member(out, "Contents/content.hpf") == package
    assert _foreign_t(out) == 0
    after_guides = run_hwpx_acceptance(out)
    assert after_guides.guides == 1
    assert "작성방법" in after_guides.guides_samples[0]
    assert src.read_bytes() == before_bytes
    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha
    _assert_no_auto(src)
    _assert_no_auto(out)

    submitted = tmp_path / "submitted.hwpx"
    submit = submit_hwpx(
        src, submitted,
        identity=_identity(),
        normalize_colors=False,
        submission_cleanup=False,
    )
    final = Path(submit.final)
    submitted_cells = _cells(final)
    _assert_structure_held(before_cells, submitted_cells, {
        (0, 1, 1): ["서울"],
        (0, 6, 1): ["홍길동"],
        (0, 7, 1): ["□개인 ■법인"],
        (0, 10, 1): ["침범"],
        (0, 12, 1): ["부산"],
        (0, 13, 1): ["첫번째"],
        (0, 15, 1): ["99"],
        (1, 0, 1): ["자식회사"],
    })
    assert _at(submitted_cells, 3, 0, 1)["texts"] == [""]
    assert _at(submitted_cells, 4, 0, 1)["texts"] == [""]
    assert _at(submitted_cells, 0, 14, 1)["texts"] == [""]
    assert "02" not in _all_texts(final)
    assert "팩스" in submit.residual
    assert "직원명" in submit.residual
    assert any(note == "[t02] 팩스 AUTHORIZATION_PENDING" for note in submit.notes)
    assert any(note == "[repeated-row] 직원명 row=14 col=1 UNFILLED" for note in submit.notes)
    assert any(note.startswith("[duplicate-label] 팩스 ") for note in submit.notes)
    assert not any("팩스" in note and note.endswith("GRANT_WRITTEN") for note in submit.notes)
    assert "[t02] 속기업명 GRANT_WRITTEN" in submit.notes
    assert "[t02] 기업명 GRANT_WRITTEN" not in submit.notes
    assert not any("서명" in note and note.endswith("GRANT_WRITTEN") for note in submit.notes)
    assert _body_runs(final) == before_runs
    assert _foreign_t(final) == 0
    assert src.read_bytes() == before_bytes
    _assert_no_auto(final)


def test_combined_refuse_writes_nothing_and_keeps_source(tmp_path: Path) -> None:
    src = tmp_path / "combined.hwpx"
    sha = _hwpx(src)
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    blocked = tmp_path / "blocked.hwpx"
    refused = commit_t02_label_writes(src, blocked, {"기업명": "새회사", "주소": "서울", "팩스": "02"})
    assert refused.ok is False and refused.cancelled is True
    assert "NOT_AUTHORIZED:기업명" in refused.reasons
    assert "EXISTING_VALUE:기업명" in refused.reasons
    assert "NOT_AUTHORIZED:팩스" in refused.reasons
    assert not blocked.exists()

    guide = next(
        (section.section_member, paragraph.paragraph_index, run.run_index, text.text_node_index, text.raw_text)
        for section in index.sections
        for paragraph in section.paragraphs
        for run in paragraph.runs
        for text in run.text_nodes
        if text.raw_text == "※ 안내문입니다"
    )
    invaded = tmp_path / "invaded.hwpx"
    exact = commit_exact_text_writes(
        src, invaded,
        [ExactTextTarget(guide[0], guide[1], guide[2], guide[3], guide[4], "지워진안내")],
        source_sha256=sha,
    )
    assert exact.ok is False and exact.cancelled is True
    assert exact.reason.startswith("EXISTING_VALUE")
    assert not invaded.exists()
    mismatched = tmp_path / "sha.hwpx"
    sha_report = commit_exact_text_writes(
        src, mismatched,
        [ExactTextTarget(guide[0], guide[1], guide[2], guide[3], guide[4], "지워진안내")],
        source_sha256="0" * 64,
    )
    assert sha_report.reason == "SHA_MISMATCH"
    assert not mismatched.exists()

    f01 = tmp_path / "f01.hwpx"
    filled = fill_hwpx(
        src, f01,
        identity={"기업명": "새회사"},
        field_writes={"participant_name": "들어가면안됨"},
        expected_sha256=F01_CANONICAL_SHA256,
        force_black=False,
    )
    assert filled.template_status == "TEMPLATE_MISMATCH"
    assert filled.field_write_skipped.get("participant_name") == "TEMPLATE_MISMATCH"
    assert "들어가면안됨".encode("utf-8") not in f01.read_bytes()
    assert "새회사".encode("utf-8") not in f01.read_bytes()
    assert _at(_cells(f01), 0, 0, 1)["texts"] == ["기존회사"]
    assert sha != F01_CANONICAL_SHA256
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha


def test_synonym_still_fills_when_the_exact_label_is_absent(tmp_path: Path) -> None:
    src = tmp_path / "synonym.hwpx"
    section = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        + _wrapped(_tbl([[_cell("대표자", 0, 0), _cell("", 0, 1)]]))
        + "</hs:sec>"
    )
    with zipfile.ZipFile(src, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", b"<hh:head/>")
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(src, out, identity={"성명": "김철수"}, force_black=False)
    assert report.filled == {"성명": "김철수"}
    assert _at(_cells(out), 0, 0, 1)["texts"] == ["김철수"]
