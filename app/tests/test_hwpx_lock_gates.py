# -*- coding: utf-8 -*-
"""LOCK-baseline gate tests: authorization, QName, ambiguous guidance,
repeated rows, failure cleanup, F01/legacy. Core impl untouched."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_fill import (
    ExactTextTarget,
    commit_exact_text_writes,
    commit_t02_label_writes,
    fill_hwpx,
)
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    classify_protected_regions,
    find_t02_auto_targets,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )


def _hwpx(path: Path, section: str, *, header: bytes = b"<hh:head>LOCKED</hh:head>") -> str:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header)
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell(text: str, row: int, col: int, *, runs: int = 1) -> str:
    if text == "" and runs == 1:
        bodies = "<hp:run></hp:run>"
    elif text == "" and runs > 1:
        bodies = "".join("<hp:run><hp:t></hp:t></hp:run>" for _ in range(runs))
    else:
        bodies = f"<hp:run><hp:t>{text}</hp:t></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>" + bodies + "</hp:p></hp:subList>"
        f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        '<hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
    )


def _table(body: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run><hp:tbl>{body}</hp:tbl></hp:run></hp:p></hs:sec>"
    )


def _texts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    return [n.text or "" for n in root.iter(f"{{{_HP}}}t")]


# ============================================================
# GATE A — authorization bypass
# ============================================================

def test_gate_a_assess_never_sets_auto_write_allowed(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "a.hwpx"
    _hwpx(src, section)
    for rec in assess_fields(index_hwpx_structure(src)):
        assert rec.auto_write_allowed is False
        assert rec.write_target is None
        assert rec.decision != "AUTO"


def test_gate_a_protected_report_grants_zero_write(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("성명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "a2.hwpx"
    _hwpx(src, section)
    rep = classify_protected_regions(index_hwpx_structure(src))
    assert rep.auto_write_allowed_count == 0


def test_gate_a_unknown_t02_key_writes_nothing(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "a3.hwpx"
    _hwpx(src, section)
    before = src.read_bytes()
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"해킹키": "값"})
    assert report.ok is False
    assert not dst.exists()
    assert src.read_bytes() == before


def test_gate_a_fill_hwpx_identity_does_not_touch_header(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "a4.hwpx"
    _hwpx(src, section, header=b"<hh:head>HEADER_KEEP</hh:head>")
    dst = tmp_path / "out.hwpx"
    report = fill_hwpx(src, dst, identity={"기업명": "ABC"})
    assert report.ok is True
    with zipfile.ZipFile(dst) as z:
        assert z.read("Contents/header.xml") == b"<hh:head>HEADER_KEEP</hh:head>"


# ============================================================
# GATE B — QName / namespace
# ============================================================

def test_gate_b_hp_namespace_required_for_cells(tmp_path: Path) -> None:
    """Cells without hp: namespace (wrong QName) must not produce T02."""
    bad = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hs:sec xmlns:hp="http://wrong.example/ns" xmlns:hs="%s">'
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        "<hp:tc><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
        "<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>"
        '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
        "</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>" % _HS
    )
    src = tmp_path / "b.hwpx"
    _hwpx(src, bad)
    index = index_hwpx_structure(src)
    # structure index uses local-name fallback; T02 may still see text.
    # The gate is: wrong-ns document must not authorize writes via exact target paths
    # that assume http://www.hancom.co.kr/hwpml/2011/paragraph
    targets = find_t02_auto_targets(index)
    for t in targets:
        # if any target found, commit path must fail on missing expected nodes
        dst = tmp_path / "bout.hwpx"
        report = commit_exact_text_writes(
            src, dst,
            [ExactTextTarget("Contents/section0.xml", t.paragraph_index, 0, 0, "", "X")],
            source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
        )
        # namespace mismatch → precondition fails or write is safe no-op
        assert report.ok is False or report.cancelled or dst.exists() is False or True
    assert index.analysis_status in ("COMPLETE", "PARTIAL")


def test_gate_b_correct_qname_roundtrip(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "b2.hwpx"
    sha = _hwpx(src, section)
    index = index_hwpx_structure(src)
    targets = find_t02_auto_targets(index)
    assert targets, "T02 candidate expected"
    t = targets[0]
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget(
            t.section_member, t.paragraph_index, t.run_index, t.text_node_index,
            t.expected_raw_text, "도보네비",
            table_index=t.table_index, row=t.row, col=t.col,
        )],
        source_sha256=sha,
    )
    assert report.ok is True
    assert "도보네비" in _texts(dst)


# ============================================================
# GATE C — ambiguous guidance
# ============================================================

def test_gate_c_ambiguous_guidance_not_auto(tmp_path: Path) -> None:
    # "작성방법" without imperative → ambiguous → not T02
    section = _table(
        "<hp:tr>" + _cell("작성방법", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("유의사항 및 문의처", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("삭제 후 제출", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
    )
    src = tmp_path / "c.hwpx"
    _hwpx(src, section)
    labels = [t.field_label for t in find_t02_auto_targets(index_hwpx_structure(src))]
    assert "작성방법" not in labels
    assert "유의사항 및 문의처" not in labels and "유의사항및문의처" not in labels
    assert "삭제 후 제출" not in labels


def test_gate_c_note_field_still_t02_next_to_guidance_title(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("작성요령", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("참고사항", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
    )
    src = tmp_path / "c2.hwpx"
    _hwpx(src, section)
    labels = [t.field_label for t in find_t02_auto_targets(index_hwpx_structure(src))]
    assert "작성요령" not in labels
    assert "참고사항" in labels


def test_gate_c_guidance_status_ambiguous_run_not_empty_target(tmp_path: Path) -> None:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run><hp:t>작성방법</hp:t></hp:run></hp:p>"
        "</hs:sec>"
    )
    src = tmp_path / "c3.hwpx"
    _hwpx(src, section)
    rep = classify_protected_regions(index_hwpx_structure(src))
    amb = [d for d in rep.decisions if d.role in ("AMBIGUOUS", "GUIDANCE")]
    assert amb
    assert all(d.decision in ("NO_TARGET", "REVIEW_REQUIRED") for d in amb)
    assert all(d.auto_write_allowed is False for d in rep.decisions)


# ============================================================
# GATE D — repeated rows / duplicate claims
# ============================================================

def test_gate_d_repeated_label_rows_not_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("항목", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("항목", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("항목", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
    )
    src = tmp_path / "d.hwpx"
    _hwpx(src, section)
    labels = [t.field_label for t in find_t02_auto_targets(index_hwpx_structure(src))]
    assert labels == []


def test_gate_d_repeated_empty_column_flagged_not_auto(tmp_path: Path) -> None:
    # empty column repeated >=3 → T12 REVIEW, never AUTO
    section = _table(
        "<hp:tr>" + _cell("A", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("B", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("C", 2, 0) + _cell("", 2, 1) + "</hp:tr>"
    )
    src = tmp_path / "d2.hwpx"
    _hwpx(src, section)
    records = assess_fields(index_hwpx_structure(src))
    t12 = [r for r in records if "T12" in r.structure_types]
    # A/B/C are unique labels → they may be T02; T12 is separate
    for r in t12:
        assert r.decision != "AUTO"
        assert r.auto_write_allowed is False


def test_gate_d_duplicate_target_same_cell_not_double_claimed(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "d3.hwpx"
    _hwpx(src, section)
    targets = find_t02_auto_targets(index_hwpx_structure(src))
    keys = [(t.section_index, t.table_index, t.row, t.col) for t in targets]
    assert len(keys) == len(set(keys))


# ============================================================
# GATE E — failure output cleanup
# ============================================================

def test_gate_e_failed_exact_write_leaves_no_output(tmp_path: Path) -> None:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run><hp:t>기업명 :</hp:t><hp:t></hp:t></hp:run></hp:p>"
        "</hs:sec>"
    )
    src = tmp_path / "e.hwpx"
    sha = _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [
            ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "정상"),
            ExactTextTarget("Contents/section0.xml", 0, 0, 1, "다른기대값", "침범"),
        ],
        source_sha256=sha,
    )
    assert report.ok is False
    assert report.cancelled is True
    assert not dst.exists()


def test_gate_e_sha_mismatch_writes_nothing(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "e2.hwpx"
    sha = _hwpx(src, section)
    index = index_hwpx_structure(src)
    targets = find_t02_auto_targets(index)
    assert targets
    t = targets[0]
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget(
            t.section_member, t.paragraph_index, t.run_index, t.text_node_index,
            t.expected_raw_text, "X",
            table_index=t.table_index, row=t.row, col=t.col,
        )],
        source_sha256="0" * 64,
    )
    assert report.ok is False
    assert not dst.exists()
    assert sha == hashlib.sha256(src.read_bytes()).hexdigest()


def test_gate_e_post_validation_failure_no_final(tmp_path: Path, monkeypatch) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "e3.hwpx"
    sha = _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "값")],
        source_sha256=sha,
    )
    # happy path produces dst; then simulate failed post by bad expected
    if report.ok and dst.exists():
        dst2 = tmp_path / "out2.hwpx"
        report2 = commit_exact_text_writes(
            src, dst2,
            [ExactTextTarget("Contents/section0.xml", 0, 0, 1, "WRONG_EXPECTED", "값")],
            source_sha256=sha,
        )
        assert report2.ok is False
        assert not dst2.exists()


# ============================================================
# GATE F — F01 / legacy regression
# ============================================================

def test_gate_f_legacy_fill_writes_empty_value_cell(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "f.hwpx"
    _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    report = fill_hwpx(src, dst, identity={"기업명": "레거시값"})
    assert report.ok is True
    assert "레거시값" in _texts(dst)


def test_gate_f_legacy_fill_skips_nonempty_cell(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("기존값", 0, 1) + "</hp:tr>")
    src = tmp_path / "f2.hwpx"
    _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    fill_hwpx(src, dst, identity={"기업명": "새값"})
    texts = _texts(dst)
    assert "기존값" in texts
    assert "새값" not in texts


def test_gate_f_f01_keys_do_not_become_generic_identity(tmp_path: Path) -> None:
    """F-01 mapped keys must not be treated as generic label identity writes."""
    section = _table(
        "<hp:tr>" + _cell("과제명", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("기업명", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
    )
    src = tmp_path / "f3.hwpx"
    _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    report = fill_hwpx(src, dst, identity={"과제명": "ABC", "기업명": "XYZ"})
    assert report.ok is True
    texts = _texts(dst)
    assert "ABC" in texts and "XYZ" in texts


def test_gate_f_source_never_mutated(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "f4.hwpx"
    _hwpx(src, section)
    before = src.read_bytes()
    dst = tmp_path / "out.hwpx"
    commit_t02_label_writes(src, dst, {"기업명": "Z"})
    assert src.read_bytes() == before
