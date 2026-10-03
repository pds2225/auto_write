"""기업 프로필 → HWPX 직접채움 라벨. 숫자 사실값과 팀명을 유지한다."""

from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document

from auto_write.models import ProjectInput
from auto_write.services.company_identity import (
    build_direct_fill_identity,
    company_profile_identity,
    identity_from_reference_path,
)
from auto_write.services.hwpx_fill import fill_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def test_profile_maps_standard_fields_and_keeps_numbers() -> None:
    identity = company_profile_identity({
        "name": "별칭기업",
        "기업명": "도보네비",
        "representative": "김대표",
        "team_name": "기획팀",
        "business_number": "123-45-67890",
        "phone": "02-000-0000",
        "address": "서울시 중구",
        "founded": "2020-01-01",
        "email": "a@example.com",
        "빈값": "  ",
        "특이항목": "그대로",
    })
    assert list(identity)[:3] == ["기업명", "대표자", "팀명"]
    assert identity["기업명"] == "도보네비"
    assert identity["대표자"] == "김대표"
    assert identity["팀명"] == "기획팀"
    assert identity["사업자등록번호"] == "123-45-67890"
    assert identity["연락처"] == "02-000-0000"
    assert identity["주소"] == "서울시 중구"
    assert identity["설립일"] == "2020-01-01"
    assert identity["이메일"] == "a@example.com"
    assert identity["특이항목"] == "그대로"
    assert "빈값" not in identity


def test_explicit_hwpx_identity_wins_over_profile() -> None:
    project = ProjectInput(
        template_id="t1",
        organization_profile={
            "name": "프로필기업",
            "대표자": "김대표",
            "팀명": "기획팀",
        },
        project_meta={"hwpx_identity": {"기업명": "명시기업"}},
    )
    identity = build_direct_fill_identity(project)
    assert identity["기업명"] == "명시기업"
    assert identity["대표자"] == "김대표"
    assert identity["팀명"] == "기획팀"


def test_direct_fill_maps_user_authored_overview_without_fabrication() -> None:
    project = ProjectInput(
        template_id="t1",
        answers={"user_notes": "사용자가 직접 입력한 창업아이템 개요"},
    )
    identity = build_direct_fill_identity(project)
    assert identity["창업아이템 개요"] == "사용자가 직접 입력한 창업아이템 개요"

    preferred = ProjectInput(
        template_id="t1",
        answers={"user_brief": "사용자 사업 개요", "user_notes": "추가 메모"},
    )
    identity2 = build_direct_fill_identity(preferred)
    assert identity2["창업아이템 개요"] == "사용자 사업 개요"

def test_docx_reference_keeps_registration_number_and_team(tmp_path: Path) -> None:
    doc = Document()
    table = doc.add_table(rows=4, cols=2)
    rows = (
        ("기업명", "도보네비"),
        ("팀명", "기획팀"),
        ("대표자", "김대표"),
        ("사업자등록번호", "123-45-67890"),
    )
    for index, (label, value) in enumerate(rows):
        table.rows[index].cells[0].text = label
        table.rows[index].cells[1].text = value
    path = tmp_path / "company.docx"
    doc.save(path)
    identity = identity_from_reference_path(path)
    assert identity["기업명"] == "도보네비"
    assert identity["팀명"] == "기획팀"
    assert identity["대표자"] == "김대표"
    assert identity["사업자등록번호"] == "123-45-67890"


def _cell(col: int, row: int, text: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def test_team_and_company_fill_their_own_cells(tmp_path: Path) -> None:
    """팀명 칸이 기업명보다 앞에 있어도 각자 값만 들어간다."""
    rows = (
        f"<hp:tr>{_cell(0, 0, '팀명')}{_cell(1, 0, '')}</hp:tr>"
        f"<hp:tr>{_cell(0, 1, '기업명')}{_cell(1, 1, '')}</hp:tr>"
        f"<hp:tr>{_cell(0, 2, '대표자')}{_cell(1, 2, '')}</hp:tr>"
    )
    section = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="3" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    src = tmp_path / "form.hwpx"
    out = tmp_path / "out.hwpx"
    with zipfile.ZipFile(src, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/section0.xml", section)
    report = fill_hwpx(src, out, identity={
        "기업명": "도보네비",
        "팀명": "기획팀",
        "대표자": "김대표",
    })
    xml = zipfile.ZipFile(out).read("Contents/section0.xml").decode("utf-8")
    assert report.filled["팀명"] == "기획팀"
    assert report.filled["기업명"] == "도보네비"
    assert report.filled["대표자"] == "김대표"
    assert "기획팀" in xml and "도보네비" in xml
