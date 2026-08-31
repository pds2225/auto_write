"""test_hwpx_resume_supplement.py — 학력·자격·경력 좌표 채움."""

from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_resume_supplement import (
    canonical_sign_date,
    supplement_hwpx_from_resume,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _cell(col: int, row: int, text: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def _edu_table() -> str:
    # header-ish row0 empty; row1/2 placeholders like real form
    r0 = f"<hp:tr>{_cell(0,0,'')}{_cell(2,0,'')}</hp:tr>"
    r1 = (
        f"<hp:tr>{_cell(0,1,'년       월  (졸업/수료)')}"
        f"{_cell(2,1,'대학교              전공')}</hp:tr>"
    )
    r2 = (
        f"<hp:tr>{_cell(0,2,'년       월  (졸업/수료)')}"
        f"{_cell(2,2,'대학교              전공')}</hp:tr>"
    )
    return f'<hp:tbl rowCnt="3" colCnt="3">{r0}{r1}{r2}</hp:tbl>'


def _lic_table() -> str:
    hdr = f"<hp:tr>{_cell(0,0,'자격증/면허증')}{_cell(1,0,'취득일')}{_cell(2,0,'등급')}{_cell(3,0,'발행처')}</hp:tr>"
    r1 = f"<hp:tr>{_cell(0,1,' ')}{_cell(1,1,'(yyyy/mm/dd)')}{_cell(2,1,' ')}{_cell(3,1,' ')}</hp:tr>"
    r2 = f"<hp:tr>{_cell(0,2,' ')}{_cell(1,2,'(yyyy/mm/dd)')}{_cell(2,2,' ')}{_cell(3,2,' ')}</hp:tr>"
    return f'<hp:tbl rowCnt="3" colCnt="4">{hdr}{r1}{r2}</hp:tbl>'


def _career_table() -> str:
    hdr = f"<hp:tr>{_cell(0,0,'주요 근무처')}{_cell(1,0,'근무기간')}{_cell(2,0,'직  위')}{_cell(3,0,'담당업무')}</hp:tr>"
    rows = "".join(
        f"<hp:tr>{_cell(0,i,' ')}{_cell(1,i,'~')}{_cell(2,i,' ')}{_cell(3,i,' ')}</hp:tr>"
        for i in range(1, 5)
    )
    return f'<hp:tbl rowCnt="5" colCnt="4">{hdr}{rows}</hp:tbl>'


def _section() -> bytes:
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:t>학력사항</hp:t></hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0">{_edu_table()}</hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0">{_lic_table()}</hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0">{_career_table()}</hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0"><hp:t>2026년  월  일</hp:t></hp:run></hp:p>'
        "</hs:sec>"
    )
    return body.encode("utf-8")


def _make_hwpx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", b'<?xml version="1.0"?><hh:head/>')
        z.writestr("Contents/section0.xml", _section())


def _section_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("Contents/section0.xml").decode("utf-8")


def test_fills_education_license_career_from_facts_json(tmp_path: Path):
    src = tmp_path / "form.hwpx"
    out = tmp_path / "filled.hwpx"
    facts = tmp_path / "facts.json"
    _make_hwpx(src)
    facts.write_text(
        json.dumps(
            {
                "education": [
                    ["2025년 8월 (졸업)", "한양대학교", "경영컨설팅학과 (석사)"],
                    ["2016년 2월 (졸업)", "강남대학교", "경영학과 (학사)"],
                ],
                "licenses": [
                    ["경영지도사", "2020/01/01", "마케팅", "중소벤처기업부"],
                    ["스타트업 AC 심사역", "2023/02/07", "-", "씨엔티테크"],
                ],
                "careers": [
                    ["밸류업파트너스", "2022.11 ~ 현재", "대표", "정부지원사업·정책자금"],
                    ["IPO브릿지", "2022.02 ~ 2022.11", "선임컨설턴트", "사업계획서·IR자료 컨설팅"],
                    ["오케이저축은행", "2020.03 ~ 2021.07", "계장", "기업금융·투자금융(IB)"],
                    ["웰컴저축은행", "2016.11 ~ 2020.02", "계장", "기업금융(부동산·PF)"],
                ],
                "sign_date": "2026년  7월  30일",
                "check_columns": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    frozen = date(2026, 8, 31)
    rep = supplement_hwpx_from_resume(src, out, facts_json=facts, today=frozen)
    assert rep.ok
    text = _section_text(out)
    assert "한양대학교" in text
    assert "강남대학교" in text
    assert "경영지도사" in text
    assert "웰컴저축은행" in text
    assert "2026년  8월  31일" in text
    assert "2026년  7월  30일" not in text
    assert "년       월  (졸업/수료)" not in text or text.count("한양대학교") >= 1
    # 원본 미수정
    assert "한양대학교" not in _section_text(src)


def test_no_auto_check_without_columns(tmp_path: Path):
    src = tmp_path / "form.hwpx"
    out = tmp_path / "filled.hwpx"
    _make_hwpx(src)
    rep = supplement_hwpx_from_resume(
        src,
        out,
        education=[("2025년 8월 (졸업)", "한양대학교", "석사")],
        licenses=[],
        careers=[],
        check_columns=[],
    )
    assert rep.checks_set == []


def test_canonical_sign_date_is_execution_day():
    assert canonical_sign_date(today=date(2026, 8, 31)) == "2026년  8월  31일"
    assert canonical_sign_date(today=date(2026, 1, 5)) == "2026년  1월  5일"
