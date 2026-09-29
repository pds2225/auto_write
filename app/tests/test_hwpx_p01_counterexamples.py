# -*- coding: utf-8 -*-
"""Counterexample / regression / qualification tests for P0-P1 Target Form Analyzer.

No core implementation is modified here. Failures are reported with
reproduction conditions only.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from auto_write.services.hwpx_fill import commit_exact_text_writes, commit_t02_label_writes, ExactTextTarget
from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    assess_fields,
    classify_protected_regions,
    find_t02_auto_targets,
    _t02_label,
    _sign_consent_label,
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


def _hwpx(path: Path, section: str, *, with_hpf: bool = True) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", b"<hh:head>LOCKED</hh:head>")
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        if with_hpf:
            archive.writestr("Contents/content.hpf", _hpf().encode("utf-8"))


def _cell(text: str, row: int, col: int, *, runs: int = 1, span: str = "1") -> str:
    if text == "" and runs == 1:
        bodies = "<hp:run></hp:run>"
    elif text == "" and runs > 1:
        bodies = "".join("<hp:run><hp:t></hp:t></hp:run>" for _ in range(runs))
    else:
        bodies = f"<hp:run><hp:t>{text}</hp:t></hp:run>"
    return (
        "<hp:tc><hp:subList><hp:p>"
        + bodies
        + "</hp:p></hp:subList>"
        + f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/>'
        + f'<hp:cellSpan rowSpan="1" colSpan="{span}"/></hp:tc>'
    )


def _table(body: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"<hp:p><hp:run><hp:tbl>{body}</hp:tbl></hp:run></hp:p></hs:sec>"
    )


def _labels(path: Path) -> list[str]:
    return [t.field_label for t in find_t02_auto_targets(index_hwpx_structure(path))]


# ---------------------------------------------------------------------------
# REGRESSION: consent / pledge leaks that previously became AUTO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label",
    [
        "과제사업계획서작성투자동의",
        "동의하지않음",
        "▪선정결과통보▪이행확약서제출(지원기업→전담기관(NIPA))",
        "개인정보수집이용동의서",
        "보안서약서",
        "이행확약서",
    ],
)
def test_regression_consent_pledge_labels_are_never_t02(label: str) -> None:
    """Repro: _t02_label(label) must be None. Previously bare 동의/확약 slipped through."""
    assert _t02_label(label) is None
    assert _sign_consent_label(label.replace(" ", "")) or label.startswith("▪")


def test_regression_참고n_hyphen_reference_titles_are_not_t02() -> None:
    """Repro: 참고9-1 was allowed because 참고N regex lacked hyphen."""
    for lab in ("참고9-1", "참고 9-2", "참고1", "예시1", "예시 2"):
        assert _t02_label(lab) is None, lab


def test_regression_guidance_section_titles_are_not_t02() -> None:
    for lab in ("사업안내", "작성요령", "성과목표작성요령", "유의사항및문의처", "(예시)미세먼지"):
        assert _t02_label(lab) is None, lab


# ---------------------------------------------------------------------------
# QUALIFICATION: note fields and normal inputs must stay
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label",
    ["참고사항", "유의사항", "지원대상참고사항", "부서명", "겸직인력현황", "기업명", "성명", "주소", "대표자명"],
)
def test_qualification_note_and_normal_labels_stay_t02(label: str) -> None:
    assert _t02_label(label) == label.replace(" ", "")


def test_qualification_unique_label_empty_cell_is_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
    )
    src = tmp_path / "q.hwpx"
    _hwpx(src, section)
    labels = _labels(src)
    assert labels == ["기업명"]


# ---------------------------------------------------------------------------
# COUNTEREXAMPLES: shapes that must NOT become T02 / AUTO
# ---------------------------------------------------------------------------

def test_counterexample_nonunique_label_is_not_t02(tmp_path: Path) -> None:
    """Two cells labeled 기업명 → counted twice → neither is T02."""
    section = _table(
        "<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("기업명", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
    )
    src = tmp_path / "dup.hwpx"
    _hwpx(src, section)
    assert "기업명" not in _labels(src)


def test_counterexample_value_cell_with_text_is_not_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("기업명", 0, 0) + _cell("이미 값", 0, 1) + "</hp:tr>"
    )
    src = tmp_path / "filled.hwpx"
    _hwpx(src, section)
    assert _labels(src) == []


def test_counterexample_multi_run_empty_value_is_not_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1, runs=2) + "</hp:tr>"
    )
    src = tmp_path / "multirun.hwpx"
    _hwpx(src, section)
    assert _labels(src) == []


def test_counterexample_guidance_neighbor_blocks_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>"
        + _cell("기업명", 0, 0)
        + _cell("", 0, 1)
        + _cell("※ 삭제 후 제출", 0, 2)
        + "</hp:tr>"
    )
    src = tmp_path / "guide-nb.hwpx"
    _hwpx(src, section)
    assert _labels(src) == []


def test_counterexample_choice_marks_are_not_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("◯ 동의  ◯ 비동의", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
        "<hp:tr>" + _cell("□예", 1, 0) + _cell("", 1, 1) + "</hp:tr>"
    )
    src = tmp_path / "choice.hwpx"
    _hwpx(src, section)
    labels = _labels(src)
    assert labels == []


def test_counterexample_date_scaffold_label_is_not_t02(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("2024년", 0, 0) + _cell("", 0, 1) + _cell("월", 0, 2) + _cell("", 0, 3) + "</hp:tr>"
    )
    src = tmp_path / "date.hwpx"
    _hwpx(src, section)
    labels = _labels(src)
    assert "2024년" not in labels
    assert "월" not in labels


def test_counterexample_spanned_value_cell_is_not_t02(tmp_path: Path) -> None:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}"><hp:p><hp:run><hp:tbl>'
        "<hp:tr>"
        + _cell("대표", 0, 0)
        + (
            "<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>"
            '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="2" colSpan="1"/></hp:tc>'
        )
        + "</hp:tr><hp:tr>"
        + _cell("총괄", 1, 0)
        + "</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>"
    )
    src = tmp_path / "span.hwpx"
    _hwpx(src, section)
    labels = _labels(src)
    assert "대표" not in labels and "총괄" not in labels


def test_counterexample_partial_analysis_yields_no_t02(tmp_path: Path) -> None:
    """No content.hpf → PARTIAL → find_t02 returns empty (no AUTO on unstable analysis)."""
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "partial.hwpx"
    _hwpx(src, section, with_hpf=False)
    index = index_hwpx_structure(src)
    assert index.analysis_status == "PARTIAL"
    assert find_t02_auto_targets(index) == ()


def test_counterexample_unit_atoms_are_not_t02() -> None:
    for lab in ("대", "식", "개", "명", "원", "2024년", "5월", "3일", "서식5", "서식 5"):
        assert _t02_label(lab) is None, lab


def test_counterexample_assess_fields_never_grants_auto_write(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "assess.hwpx"
    _hwpx(src, section)
    records = assess_fields(index_hwpx_structure(src))
    assert records
    for rec in records:
        assert rec.auto_write_allowed is False
        assert rec.write_target is None
        assert rec.decision != "AUTO"


def test_counterexample_protected_regions_never_allow_write(tmp_path: Path) -> None:
    section = _table(
        "<hp:tr>" + _cell("성 명 : (서명)", 0, 0) + _cell("", 0, 1) + "</hp:tr>"
    )
    src = tmp_path / "prot.hwpx"
    _hwpx(src, section)
    report = classify_protected_regions(index_hwpx_structure(src))
    assert report.auto_write_allowed_count == 0


# ---------------------------------------------------------------------------
# P0-3 QUALIFICATION: exact write plan cancellation
# ---------------------------------------------------------------------------

def test_qualification_exact_write_keeps_untouched_nodes(tmp_path: Path) -> None:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run><hp:t>기업명 :</hp:t><hp:t></hp:t></hp:run></hp:p>"
        "<hp:p><hp:run><hp:t>※ 안내문</hp:t></hp:run></hp:p>"
        "</hs:sec>"
    )
    src = tmp_path / "exact.hwpx"
    _hwpx(src, section)
    import hashlib
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "주식회사")],
        source_sha256=sha,
    )
    assert report.ok is True
    assert src.read_bytes()  # source untouched
    texts = []
    from lxml import etree
    with zipfile.ZipFile(dst) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
        texts = [n.text or "" for n in root.iter(f"{{{_HP}}}t")]
    assert "주식회사" in texts
    assert "※ 안내문" in texts
    assert "기업명 :" in texts


def test_qualification_t02_write_refuses_unknown_key(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "t02w.hwpx"
    _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"존재하지않는키": "값"})
    assert report.ok is False


def test_qualification_t02_write_happy_path_keeps_label(tmp_path: Path) -> None:
    section = _table("<hp:tr>" + _cell("기업명", 0, 0) + _cell("", 0, 1) + "</hp:tr>")
    src = tmp_path / "t02ok.hwpx"
    _hwpx(src, section)
    dst = tmp_path / "out.hwpx"
    report = commit_t02_label_writes(src, dst, {"기업명": "도보네비"})
    assert report.ok is True
    from lxml import etree
    with zipfile.ZipFile(dst) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
        texts = [n.text or "" for n in root.iter(f"{{{_HP}}}t")]
    assert "기업명" in texts and "도보네비" in texts
