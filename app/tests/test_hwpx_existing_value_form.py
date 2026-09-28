# -*- coding: utf-8 -*-
"""Gate: forms that already hold a real value.

A non-empty prose or number cell is not a T02 grant and is not overwritten by
identity, replacements, F01, or an exact write. The skip stays visible as
EXISTING_VALUE. Empty cells and prior placeholder gates (____, 0000년…, □)
keep their own behavior.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from lxml import etree

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
    classify_protected_regions,
    find_t02_auto_targets,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _hwpx(path: Path, section: str) -> str:
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell(text: str, row: int, col: int) -> str:
    body = f"<hp:run><hp:t>{text}</hp:t></hp:run>" if text else "<hp:run><hp:t></hp:t></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>" + body + "</hp:p></hp:subList>"
        f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        '<hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _row(pairs: list[tuple[str, str]], row: int) -> str:
    return "<hp:tr>" + _cell(pairs[0], row, 0) + _cell(pairs[1], row, 1) + "</hp:tr>"


def _table(rows: list[tuple[str, str]]) -> str:
    body = "".join(_row(pair, index) for index, pair in enumerate(rows))
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run><hp:tbl>{body}</hp:tbl></hp:run></hp:p></hs:sec>"
    )


def _sec(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    )


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    return [node.text or "" for node in root.iter(f"{{{_HP}}}t")]


def _joined(path: Path) -> str:
    return "".join(_texts(path))


def _no_auto(path: Path) -> None:
    fields = assess_fields(index_hwpx_structure(path))
    assert fields
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)


def test_real_value_is_not_a_t02_grant(tmp_path: Path) -> None:
    src = tmp_path / "mixed.hwpx"
    _hwpx(src, _table([
        ("기업명", "기존회사"),
        ("주소", ""),
        ("매출액", "1200"),
    ]))
    index = index_hwpx_structure(src)
    assert index.analysis_status == "COMPLETE"
    assert [item.field_label for item in find_t02_auto_targets(index)] == ["주소"]
    assert [item.field_label for item in authorize_t02_writes(index)] == ["주소"]
    fields = assess_fields(index)
    assert all(field.decision != "AUTO" and field.auto_write_allowed is False for field in fields)
    existing = [field for field in fields if "EXISTING_VALUE" in field.review_reason]
    assert existing
    assert all(field.auto_write_allowed is False and field.decision == "NO_TARGET" for field in existing)
    decisions = classify_protected_regions(index).decisions
    assert any(
        decision.role == "EXISTING_VALUE" and decision.observed_text == "기존회사"
        for decision in decisions
    )
    assert all(decision.auto_write_allowed is False for decision in decisions)


def test_identity_keeps_real_value_fills_empty_and_notes(tmp_path: Path) -> None:
    src = tmp_path / "mixed.hwpx"
    sha = _hwpx(src, _table([
        ("기업명", "기존회사"),
        ("주소", ""),
        ("매출액", "1200"),
        ("한줄소개", "설립을 마쳤다"),
    ]))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src, out,
        identity={"기업명": "새회사", "주소": "서울", "매출액": "9999", "한줄소개": "다시 씀"},
        force_black=False,
    )
    texts = _texts(out)
    assert "기존회사" in texts and "1200" in texts and "설립을 마쳤다" in texts
    assert "서울" in texts
    assert "새회사" not in texts and "9999" not in texts and "다시 씀" not in texts
    assert report.filled.get("주소") == "서울"
    assert "기업명" in report.residual and "매출액" in report.residual and "한줄소개" in report.residual
    assert "[existing] 기업명 row=0 col=1 EXISTING_VALUE" in report.notes
    assert "[existing] 매출액 row=2 col=1 EXISTING_VALUE" in report.notes
    assert "[existing] 한줄소개 row=3 col=1 EXISTING_VALUE" in report.notes
    assert not any(note.endswith("GRANT_WRITTEN") for note in report.notes)
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha
    _no_auto(src)
    _no_auto(out)


def test_submit_keeps_existing_value_and_writes_the_empty_cell(tmp_path: Path) -> None:
    src = tmp_path / "mixed.hwpx"
    _hwpx(src, _table([("기업명", "기존회사"), ("주소", "")]))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = submit_hwpx(
        src, out,
        identity={"기업명": "새회사", "주소": "서울"},
        normalize_colors=False, submission_cleanup=False,
    )
    final = Path(report.final)
    texts = _texts(final)
    assert "기존회사" in texts and "서울" in texts and "새회사" not in texts
    assert "기업명" in report.residual
    assert "[existing] 기업명 row=0 col=1 EXISTING_VALUE" in report.notes
    assert any(note == "[t02] 주소 GRANT_WRITTEN" for note in report.notes)
    assert not any("기업명" in note and note.endswith("GRANT_WRITTEN") for note in report.notes)
    assert src.read_bytes() == before
    _no_auto(final)


def test_commit_refuses_existing_value_and_keeps_source(tmp_path: Path) -> None:
    src = tmp_path / "mixed.hwpx"
    sha = _hwpx(src, _table([("기업명", "기존회사"), ("주소", "")]))
    before = src.read_bytes()
    blocked = tmp_path / "blocked.hwpx"
    refused = commit_t02_label_writes(src, blocked, {"기업명": "새회사"})
    assert refused.ok is False and refused.cancelled is True
    assert "NOT_AUTHORIZED:기업명" in refused.reasons
    assert "EXISTING_VALUE:기업명" in refused.reasons
    assert not blocked.exists()
    mixed = tmp_path / "mixed-out.hwpx"
    both = commit_t02_label_writes(src, mixed, {"기업명": "새회사", "주소": "서울"})
    assert both.ok is False and not mixed.exists()
    assert "EXISTING_VALUE:기업명" in both.reasons
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha
    written = tmp_path / "written.hwpx"
    report = commit_t02_label_writes(src, written, {"주소": "서울"})
    assert report.ok is True
    assert "서울" in _texts(written) and "기존회사" in _texts(written) and "새회사" not in _texts(written)
    assert src.read_bytes() == before


def test_exact_writer_refuses_prefilled_text_node(tmp_path: Path) -> None:
    src = tmp_path / "prefilled.hwpx"
    sha = _hwpx(src, _table([("기업명", "기존회사")]))
    before = src.read_bytes()
    index = index_hwpx_structure(src)
    node = next(
        (section.section_member, paragraph.paragraph_index, run.run_index, text.text_node_index, text.raw_text)
        for section in index.sections
        for paragraph in section.paragraphs
        for run in paragraph.runs
        for text in run.text_nodes
        if text.raw_text == "기존회사"
    )
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget(node[0], node[1], node[2], node[3], node[4], "새회사")],
        source_sha256=sha,
    )
    assert report.ok is False and report.cancelled is True
    assert report.reason.startswith("EXISTING_VALUE")
    assert not dst.exists()
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha


def test_same_label_fills_only_the_empty_row(tmp_path: Path) -> None:
    src = tmp_path / "rows.hwpx"
    _hwpx(src, _table([("기업명", "기존회사"), ("기업명", "")]))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(src, out, identity={"기업명": "새회사"}, force_black=False)
    texts = _texts(out)
    assert texts.count("기업명") == 2
    assert "기존회사" in texts and "새회사" in texts
    assert "[existing] 기업명 row=0 col=1 EXISTING_VALUE" in report.notes
    assert "기업명" in report.residual
    assert find_t02_auto_targets(index_hwpx_structure(src)) == ()
    assert src.read_bytes() == before
    _no_auto(src)


def test_replacements_do_not_overwrite_real_value(tmp_path: Path) -> None:
    src = tmp_path / "repl.hwpx"
    _hwpx(src, _table([
        ("기업명", "서울특별시 강남구"),
        ("사업자등록번호", "000-00-00000"),
    ]))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src, out,
        replacements={"강남": "서초", "000-00-00000": "123-45-67890"},
        force_black=False,
    )
    texts = _texts(out)
    assert "서울특별시 강남구" in texts
    assert "서초" not in _joined(out)
    assert "123-45-67890" in texts and "000-00-00000" not in texts
    assert report.replaced == 1
    assert "[existing] 기업명 row=0 col=1 EXISTING_VALUE" in report.notes
    assert src.read_bytes() == before


def test_obvious_placeholder_still_fills_and_is_not_existing_value(tmp_path: Path) -> None:
    src = tmp_path / "ph.hwpx"
    _hwpx(src, _table([
        ("사업자등록번호", "000-00-00000"),
        ("매출액", "000억원"),
        ("작성일", "0000년 00월 00일"),
    ]))
    index = index_hwpx_structure(src)
    assert find_t02_auto_targets(index) == ()
    assert authorize_t02_writes(index) == ()
    refused = tmp_path / "refused.hwpx"
    commit = commit_t02_label_writes(src, refused, {"사업자등록번호": "123-45-67890"})
    assert commit.ok is False and not refused.exists()
    assert "NOT_AUTHORIZED:사업자등록번호" in commit.reasons
    assert not any(reason.startswith("EXISTING_VALUE:") for reason in commit.reasons)
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src, out,
        identity={
            "사업자등록번호": "123-45-67890",
            "매출액": "15억원",
            "작성일": "2026년 9월 28일",
        },
        force_black=False,
    )
    texts = _texts(out)
    assert "123-45-67890" in texts and "15억원" in texts and "2026년 9월 28일" in texts
    assert "000-00-00000" not in texts and "000억원" not in texts and "0000년 00월 00일" not in texts
    assert not any("EXISTING_VALUE" in note for note in report.notes)
    _no_auto(src)


def test_real_date_number_stays_and_inline_blank_still_fills(tmp_path: Path) -> None:
    src = tmp_path / "inline.hwpx"
    section = _sec(
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        + _cell("작성일", 0, 0) + _cell("2026년 9월 28일", 0, 1)
        + "</hp:tr></hp:tbl></hp:run></hp:p>"
        "<hp:p><hp:run><hp:t>기업명 : 기존회사</hp:t></hp:run></hp:p>"
        "<hp:p><hp:run><hp:t>주소 : ______</hp:t></hp:run></hp:p>"
    )
    _hwpx(src, section)
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src, out,
        identity={"작성일": "1999년 1월 1일", "기업명": "새회사", "주소": "서울"},
        force_black=False,
    )
    joined = _joined(out)
    assert "2026년 9월 28일" in joined and "1999년 1월 1일" not in joined
    assert "기업명 : 기존회사" in joined and "새회사" not in joined
    assert "주소 : 서울" in joined
    assert "[existing] 작성일 row=0 col=1 EXISTING_VALUE" in report.notes
    assert "[existing] 기업명 EXISTING_VALUE" in report.notes
    assert "기업명" in report.residual and "작성일" in report.residual
    assert "주소" not in report.residual
    assert src.read_bytes() == before
    assert find_t02_auto_targets(index_hwpx_structure(src)) == ()


def test_underscore_and_choice_are_not_treated_as_real_values(tmp_path: Path) -> None:
    src = tmp_path / "marks.hwpx"
    _hwpx(src, _table([
        ("소재지", "____"),
        ("사업자형태", "□개인 □법인"),
    ]))
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src, out,
        identity={"소재지": "부산", "사업자형태": "법인"},
        force_black=False,
    )
    texts = _texts(out)
    assert "____" in texts and "부산" not in texts
    assert "□개인 ■법인" in texts
    assert "소재지" in report.residual
    assert report.filled.get("사업자형태") == "법인"
    assert not any("EXISTING_VALUE" in note for note in report.notes)
    inline = tmp_path / "blank.hwpx"
    _hwpx(inline, _sec("<hp:p><hp:run><hp:t>소재지 : ______</hp:t></hp:run></hp:p>"))
    inline_out = tmp_path / "blank-out.hwpx"
    inline_report = fill_hwpx(inline, inline_out, identity={"소재지": "부산"}, force_black=False)
    assert any("부산" in text for text in _texts(inline_out))
    assert inline_report.filled.get("소재지") == "부산"
    assert not any("EXISTING_VALUE" in note for note in inline_report.notes)


def test_inline_signature_with_real_text_stays_on_signature_note(tmp_path: Path) -> None:
    src = tmp_path / "sig.hwpx"
    _hwpx(src, _sec("<hp:p><hp:run><hp:t>서명 : 홍길동</hp:t></hp:run></hp:p>"))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(src, out, identity={"서명": "김철수"}, force_black=False)
    assert _texts(out) == ["서명 : 홍길동"]
    assert report.filled == {}
    assert "서명" in report.residual
    assert "[signature] 서명 UNFILLED" in report.notes
    assert not any("EXISTING_VALUE" in note for note in report.notes)
    assert src.read_bytes() == before


def test_f01_mismatch_does_not_overwrite_existing_value(tmp_path: Path) -> None:
    src = tmp_path / "f01.hwpx"
    sha = _hwpx(src, _table([("기업명", "기존회사")]))
    before = src.read_bytes()
    out = tmp_path / "out.hwpx"
    report = fill_hwpx(
        src, out,
        identity={"기업명": "새회사"},
        field_writes={"participant_name": "들어가면안됨"},
        expected_sha256=F01_CANONICAL_SHA256,
        force_black=False,
    )
    assert report.template_status == "TEMPLATE_MISMATCH"
    assert report.field_write_skipped.get("participant_name") == "TEMPLATE_MISMATCH"
    blob = out.read_bytes()
    assert "들어가면안됨".encode("utf-8") not in blob
    assert "새회사".encode("utf-8") not in blob
    assert "기존회사" in _texts(out)
    assert "[existing] 기업명 row=0 col=1 EXISTING_VALUE" in report.notes
    assert src.read_bytes() == before
    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha
    assert sha != F01_CANONICAL_SHA256
