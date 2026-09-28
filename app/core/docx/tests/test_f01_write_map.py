# -*- coding: utf-8 -*-
"""F-01 write map: 안내문은 유지하고 지정한 paragraph/run에만 쓴다."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from lxml import etree

from auto_write.services.hwpx_fill import apply_f01_field_writes, fill_hwpx
from auto_write.services.hwpx_submit import submit_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_NS = {"hp": _HP, "hs": _HS}
_COPY = Path(r"C:\Users\ekth3\Documents\_autowrite_stage1_windows_final\F01_COPY.hwpx")


def _para(runs: list[tuple[str, str | None]], para_pr: str = "1", style: str = "0") -> str:
    body = ""
    for char, text in runs:
        node = "" if text is None else f"<hp:t>{text}</hp:t>"
        body += f'<hp:run charPrIDRef="{char}">{node}</hp:run>'
    return (
        f'<hp:p id="2147483648" paraPrIDRef="{para_pr}" styleIDRef="{style}" '
        f'pageBreak="0" columnBreak="0" merged="0">{body}'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1100" '
        'textheight="1100" baseline="935" spacing="660" horzpos="0" horzsize="100" flags="393216"/>'
        "</hp:linesegarray></hp:p>"
    )


def _cell(col: int, row: int, inner: str, *, span: str = "1") -> str:
    return (
        '<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="8">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f"{inner}</hp:subList>"
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="{span}" rowSpan="1"/>'
        '<hp:cellSz width="100" height="100"/>'
        '<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        "</hp:tc>"
    )


def _table(rows: str) -> str:
    return f"<hp:tbl>{rows}</hp:tbl>"


def _section() -> bytes:
    dummy = _table(f'<hp:tr>{_cell(0, 0, _para([("0", "x")]))}</hp:tr>')
    name = _para([("34", " 참가자(팀)명")])
    topic_label = _para([("34", " 참가작 주제")])
    summary_label = _para([("34", "참가작 주요내용 요약")])
    t2 = _table(
        "<hp:tr>"
        + _cell(0, 0, name)
        + _cell(1, 0, _para([("65", None)]))
        + "</hp:tr><hp:tr>"
        + _cell(0, 1, topic_label)
        + _cell(1, 1, _para([("67", "※ 참가작 주제는 한 문장으로 참가작 내용, 목적 등을 명확하게 파악할 수 있도록 기재하여야 함")], "39", "82"))
        + "</hp:tr><hp:tr>"
        + _cell(0, 2, summary_label)
        + "</hp:tr><hp:tr>"
        + _cell(0, 3, _para([("65", None)]), span="2")
        + "</hp:tr>"
    )
    problem = _table(
        "<hp:tr>"
        + _cell(0, 0, _para([("0", " 1. 문제 해결의 타당성")]))
        + _cell(1, 0, _para([("0", " ◈ 아이디어의 개발 동기, 배경 및 필요성")]))
        + "</hp:tr><hp:tr>"
        + _cell(0, 1, _para([("35", " "), ("49", " 1-1. 아이디어에 대한 동기(내·외부적 동기 등) 및 배경 제시")])
        + _para([("49", "  1-2. 아이디어의 필요성 및 사회적 이슈와의 관련성")], "57"), span="2")
        + "</hp:tr>"
    )
    commercial = _table(
        "<hp:tr>"
        + _cell(0, 0, _para([("0", " 2. 사업화 가능성")]))
        + _cell(1, 0, _para([("0", " ◈ 실행계획, 실현가능성 및 차별성")]))
        + "</hp:tr><hp:tr>"
        + _cell(
            0, 1,
            _para([("35", "  "), ("49", "2-1. 구체적 실행계획 및 기술적 실현 가능성 ")])
            + _para([("49", "  2-2. 유사 아이디어 대비 차별성")]),
            span="2",
        )
        + "</hp:tr>"
    )
    sustain = _table(
        "<hp:tr>"
        + _cell(0, 0, _para([("0", " 3. 지속가능성과")]) + _para([("0", "    사회적 기여")]))
        + _cell(1, 0, _para([("0", " ◈ 기술의 적절성, 성장가능성 및 공공서비스 혁신성")]))
        + "</hp:tr><hp:tr>"
        + _cell(
            0, 1,
            _para([("49", " 3-1. 기술 활용의 적절성, 발전 가능성")])
            + _para([("49", " 3-2. 기술 적용을 통한 국민 편익, 행정 효율 등 개선점 제시")])
            + _para([("49", None)]),
            span="2",
        )
        + "</hp:tr>"
    )
    entrepreneur = _table(
        "<hp:tr>"
        + _cell(0, 0, _para([("0", " 4. 기업가 정신")]))
        + _cell(1, 0, _para([("0", " ◈ 주도성 및 실행 의지")]))
        + "</hp:tr><hp:tr>"
        + _cell(
            0, 1,
            _para([("35", "  "), ("49", "4-1. 아이디어 구체화를 위해 진행한 사항")])
            + _para([("49", "  ㅇ 현장 조사, 인터뷰, 기술 검토, 유사 사례 분석 등 사전 노력 기술")])
            + _para([("49", None)]),
            span="2",
        )
        + "</hp:tr>"
    )
    tables = [dummy, dummy, t2, dummy, dummy, problem, commercial, sustain, entrepreneur]
    wrapped = "".join(f"<hp:p><hp:run>{table}</hp:run></hp:p>" for table in tables)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{wrapped}</hs:sec>'
    )
    return xml.encode("utf-8")


def _hwpx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/section0.xml", _section())


def _root(path: Path):
    with zipfile.ZipFile(path) as archive:
        return etree.fromstring(archive.read("Contents/section0.xml"))


def _texts(cell) -> list[str]:
    return [node.text or "" for node in cell.findall(".//hp:t", _NS)]


def test_f01_map_writes_only_the_mapped_runs(tmp_path: Path) -> None:
    src = tmp_path / "blank.hwpx"
    dst = tmp_path / "filled.hwpx"
    _hwpx(src)
    report = apply_f01_field_writes(src, dst, {
        "participant_name": "케이네비",
        "project_topic": "위성항법 도보 안내",
        "project_summary": "첫 문단\n둘째 문단",
        "problem_validity": "문제 본문",
        "commercialization": "사업화 본문",
        "sustainability": "지속 본문",
        "entrepreneurship": "기업가 본문",
    })
    assert report.skipped == {}
    assert set(report.written) == {
        "participant_name", "project_topic", "project_summary",
        "problem_validity", "commercialization", "sustainability", "entrepreneurship",
    }
    assert report.style_status["project_topic"] == "CONFIRMED_CHARPR_35"
    assert report.style_status["problem_validity"] == "CONFIRMED_CHARPR_35"
    assert report.style_status["commercialization"] == "CONFIRMED_CHARPR_35"
    assert "sustainability" not in report.style_status
    root = _root(dst)
    tables = root.findall(".//hp:tbl", _NS)
    name = tables[2].findall("hp:tr", _NS)[0].findall("hp:tc", _NS)[1]
    assert _texts(name) == ["케이네비"]
    topic = tables[2].findall("hp:tr", _NS)[1].findall("hp:tc", _NS)[1]
    topic_texts = _texts(topic)
    assert topic_texts[0].startswith("※ 참가작 주제는")
    assert topic_texts[1] == "위성항법 도보 안내"
    topic_run = topic.findall("hp:subList/hp:p", _NS)[1].findall("hp:run", _NS)[0]
    assert topic_run.get("charPrIDRef") == "35"
    summary = tables[2].findall("hp:tr", _NS)[3].findall("hp:tc", _NS)[0]
    assert _texts(summary) == ["첫 문단", "둘째 문단"]
    problem = tables[5].findall("hp:tr", _NS)[1].findall("hp:tc", _NS)[0]
    problem_texts = _texts(problem)
    assert problem_texts[0] == " "
    assert problem_texts[1].startswith(" 1-1.")
    assert problem_texts[-1] == "문제 본문"
    sustain = tables[7].findall("hp:tr", _NS)[1].findall("hp:tc", _NS)[0]
    sustain_texts = _texts(sustain)
    assert sustain_texts[0].startswith(" 3-1.")
    assert sustain_texts[-1] == "지속 본문"
    runs = sustain.findall("hp:subList/hp:p", _NS)[2].findall("hp:run", _NS)
    assert runs[0].get("charPrIDRef") == "49"


def test_f01_map_refuses_when_anchor_text_changes(tmp_path: Path) -> None:
    src = tmp_path / "blank.hwpx"
    dst = tmp_path / "filled.hwpx"
    xml = _section().replace(" 참가자(팀)명".encode("utf-8"), "다른라벨".encode("utf-8"))
    with zipfile.ZipFile(src, "w") as archive:
        archive.writestr("Contents/section0.xml", xml)
    report = apply_f01_field_writes(src, dst, {"participant_name": "케이네비"})
    assert "participant_name" in report.skipped
    assert report.written == {}
    with zipfile.ZipFile(dst) as archive:
        out = archive.read("Contents/section0.xml")
    assert "케이네비".encode("utf-8") not in out


@pytest.mark.skipif(not _COPY.is_file(), reason="F01_COPY.hwpx 없음")
def test_f01_map_matches_canonical_copy(tmp_path: Path) -> None:
    dst = tmp_path / "filled.hwpx"
    before = _COPY.read_bytes()
    report = apply_f01_field_writes(
        _COPY,
        dst,
        {key: f"PROBE-{key}" for key in (
            "participant_name", "project_topic", "project_summary",
            "problem_validity", "commercialization", "sustainability", "entrepreneurship",
        )},
        expected_sha256="e818bc0fa8a6ff9267b2379072e4e9e4f484f22ff7cac13b1619623e7508a187",
    )
    assert _COPY.read_bytes() == before
    assert report.skipped == {}, report.skipped
    root = _root(dst)
    tables = root.findall(".//hp:tbl", _NS)
    topic = tables[2].findall("hp:tr", _NS)[1].findall("hp:tc", _NS)[1]
    assert _texts(topic)[0].startswith("※ 참가작 주제는")
    assert "PROBE-project_topic" in _texts(topic)


_PROBE = {
    "participant_name": "PROBE-participant_name",
    "project_topic": "PROBE-project_topic",
    "project_summary": "PROBE-project_summary",
    "problem_validity": "PROBE-problem_validity",
    "commercialization": "PROBE-commercialization",
    "sustainability": "PROBE-sustainability",
    "entrepreneurship": "PROBE-entrepreneurship",
}


def test_fill_hwpx_keeps_f01_keys_out_of_identity(tmp_path: Path) -> None:
    src = tmp_path / "blank.hwpx"
    dst = tmp_path / "filled.hwpx"
    _hwpx(src)
    report = fill_hwpx(
        src, dst,
        identity={"participant_name": "IDENTITY-NAME"},
        field_writes={"participant_name": "FIELD-NAME"},
        force_black=False,
    )
    assert report.field_writes_written["participant_name"] == "RIGHT_VALUE_CELL"
    assert "participant_name" not in report.filled
    name = _root(dst).findall(".//hp:tbl", _NS)[2].findall("hp:tr", _NS)[0].findall("hp:tc", _NS)[1]
    assert _texts(name) == ["FIELD-NAME"]


@pytest.mark.skipif(not _COPY.is_file(), reason="F01_COPY.hwpx 없음")
def test_submit_hwpx_writes_f01_fields_without_touching_source(tmp_path: Path) -> None:
    dst = tmp_path / "out.hwpx"
    before = _COPY.read_bytes()
    report = submit_hwpx(
        _COPY,
        dst,
        field_writes=_PROBE,
        expected_sha256="e818bc0fa8a6ff9267b2379072e4e9e4f484f22ff7cac13b1619623e7508a187",
        preserve_template=True,
    )
    assert _COPY.read_bytes() == before
    final = Path(report.final)
    assert final.is_file()
    root = _root(final)
    tables = root.findall(".//hp:tbl", _NS)
    topic = tables[2].findall("hp:tr", _NS)[1].findall("hp:tc", _NS)[1]
    texts = _texts(topic)
    assert texts[0].startswith("※ 참가작 주제는")
    assert "PROBE-project_topic" in texts
    assert any(note.startswith("[field_writes] project_topic=") for note in report.notes)


def test_sha_mismatch_is_template_mismatch(tmp_path: Path) -> None:
    src = tmp_path / "blank.hwpx"
    dst = tmp_path / "out.hwpx"
    _hwpx(src)
    report = submit_hwpx(
        src,
        dst,
        field_writes={"participant_name": "들어가면안됨"},
        expected_sha256="e818bc0fa8a6ff9267b2379072e4e9e4f484f22ff7cac13b1619623e7508a187",
        preserve_template=True,
    )
    assert report.routing_status == "TEMPLATE_MISMATCH"
    assert report.ok is False
    assert report.submittable is False
    final = Path(report.final)
    assert final.is_file()
    assert "들어가면안됨".encode("utf-8") not in final.read_bytes()
