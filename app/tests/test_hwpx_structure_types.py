# -*- coding: utf-8 -*-
"""P1-2 and P1-3: every structure type is visible, and only T02 may be AUTO."""

from __future__ import annotations

import zipfile
from pathlib import Path

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import assess_fields

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _cell(inner: str, row: int, col: int, *, span: int = 1, address: bool = True) -> str:
    addr = (
        f'<hp:cellAddr rowAddr="{row}" colAddr="{col}"/><hp:cellSpan rowSpan="1" colSpan="{span}"/>'
        if address else ""
    )
    return f"<hp:tc><hp:subList><hp:p>{inner}</hp:p></hp:subList>{addr}</hp:tc>"


def test_all_structure_types_are_detected_and_only_t02_is_auto(tmp_path: Path) -> None:
    body = f"""
    <hp:p><hp:run><hp:t>성 명 : (서명)</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>기업명 :</hp:t></hp:run><hp:run><hp:t></hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>2025년 월 일</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>※ 이 칸은 안내문입니다</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t></hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:t>기존 본문 값</hp:t></hp:run></hp:p>
    <hp:p><hp:run><hp:tbl>
      <hp:tr>{_cell('<hp:run><hp:t>라벨없음</hp:t></hp:run>', 0, 0, address=False)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:t>기업명</hp:t></hp:run>', 1, 0)}{_cell('<hp:run></hp:run>', 1, 1)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:t>해당</hp:t></hp:run>', 2, 0)}{_cell('<hp:run></hp:run>', 2, 1)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:t>향후 채용 계획</hp:t></hp:run>', 3, 0, span=2)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:t>항목가</hp:t></hp:run>', 4, 0)}{_cell('<hp:run></hp:run>', 4, 1)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:t>항목나</hp:t></hp:run>', 5, 0)}{_cell('<hp:run></hp:run>', 5, 1)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:pic/></hp:run>', 6, 0)}</hp:tr>
      <hp:tr>{_cell('<hp:run><hp:t>바깥</hp:t></hp:run><hp:run><hp:tbl><hp:tr>' + _cell('<hp:run><hp:t>안쪽</hp:t></hp:run>', 0, 0) + '</hp:tr></hp:tbl></hp:run>', 7, 0)}</hp:tr>
    </hp:tbl></hp:run></hp:p>
    """
    later = "<hp:p><hp:run><hp:t>다음 섹션 본문</hp:t></hp:run></hp:p>"
    path = tmp_path / "types.hwpx"
    hpf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest>'
        '<opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/>'
        '<opf:item id="s1" href="Contents/section1.xml" media-type="application/xml"/>'
        '</opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/><opf:itemref idref="s1"/></opf:spine></opf:package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Contents/section0.xml", f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'.encode())
        archive.writestr("Contents/section1.xml", f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{later}</hs:sec>'.encode())
        archive.writestr("Contents/content.hpf", hpf.encode())
    records = assess_fields(index_hwpx_structure(path))
    found = {code for record in records for code in record.structure_types}
    missing = {f"T{number:02d}" for number in range(1, 17)} - found
    assert not missing
    assert all(record.auto_write_allowed is False and record.write_target is None for record in records)
    assert all(record.decision != "AUTO" for record in records)
    assert all(record.field_type != "T02" or record.eligible for record in records)
    assert all(record.field_label != "(서술 칸)" for record in records)
    guidance = [record for record in records if "T07" in record.structure_types]
    assert guidance and all(record.decision == "NO_TARGET" and record.guidance for record in guidance)
    choice = [record for record in records if "T09" in record.structure_types]
    assert choice and all(record.field_label is None for record in choice)
    assert all(record.decision != "AUTO" for record in records if "T03" in record.structure_types)
    assert all(record.decision != "AUTO" for record in records if "T05" in record.structure_types or "T06" in record.structure_types)
    assert any(record.field_label == "기업명" and record.field_type == "T02" and record.eligible and record.decision == "REVIEW_REQUIRED" for record in records)
