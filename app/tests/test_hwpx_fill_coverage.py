"""test_hwpx_fill_coverage.py + diagnose smoke."""

from __future__ import annotations

import zipfile
from pathlib import Path

from auto_write.services.hwpx_fill_coverage import score_hwpx_coverage
from hwpx_self_diagnose import diagnose_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _cell(col: int, row: int, text: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def _make_app_hwpx(path: Path) -> None:
    human = (
        f"<hp:tr>{_cell(0,0,'성명(국문)')}{_cell(1,0,'박다솜')}"
        f"{_cell(2,0,'소속/직위')}{_cell(3,0,'밸류업 / 대표')}</hp:tr>"
        f"<hp:tr>{_cell(0,1,'휴대전화')}{_cell(1,1,'010-2930-6666')}"
        f"{_cell(2,1,'생년월일')}{_cell(3,1,'1992.04.06')}</hp:tr>"
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:t>[서식 1]</hp:t></hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl>{human}</hp:tbl></hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0"><hp:t>2026년  7월  30일</hp:t></hp:run></hp:p>'
        "</hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/section0.xml", body)


def test_coverage_and_diagnose_pass(tmp_path: Path):
    p = tmp_path / "app.hwpx"
    _make_app_hwpx(p)
    cov = score_hwpx_coverage(p)
    assert cov.as_dict()["overall_rate"] >= 0
    human = next(s for s in cov.sections if s.name == "인적")
    assert human.filled >= 2
    diag = diagnose_hwpx(p)
    assert diag.ok
    assert any(g.rule == "L037" and g.status == "pass" for g in diag.gates)


def test_diagnose_fails_on_notice_blob(tmp_path: Path):
    p = tmp_path / "notice.hwpx"
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:t>모집공고 수당지급 위촉기간 접수기간 모집인원</hp:t></hp:run></hp:p>'
        "</hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(p, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/section0.xml", body)
    diag = diagnose_hwpx(p)
    assert not diag.ok
    assert any(g.rule == "L037" and g.status == "fail" for g in diag.gates)
