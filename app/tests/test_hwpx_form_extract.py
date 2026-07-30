"""test_hwpx_form_extract.py — 공고/서식 분리(L037)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from auto_write.services.hwpx_form_extract import (
    extract_forms_only,
    find_form_start_index,
    looks_like_notice_blob,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _p(text: str) -> str:
    return (
        f'<hp:p xmlns:hp="{_HP}"><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p>"
    )


def _section_with_notice_and_form() -> bytes:
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"{_p('기업민원처리센터 전문상담위원 모집공고')}"
        f"{_p('수당지급 기준 및 위촉기간 안내')}"
        f"{_p('모집인원 若干')}"
        f"{_p('[서식 1]')}"
        f"{_p('기업민원처리센터 전문상담위원 참여 신청서')}"
        f"{_p('성명(국문)')}"
        "</hs:sec>"
    )
    return body.encode("utf-8")


def _make_hwpx(path: Path, section: bytes) -> None:
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", b'<?xml version="1.0"?><hh:head/>')
        z.writestr("Contents/section0.xml", section)


def test_find_form_start_index():
    root = etree.fromstring(_section_with_notice_and_form())
    idx, marker = find_form_start_index(root)
    assert idx == 3
    assert marker == "[서식 1]"


def test_find_form_start_skips_checklist_line():
    """접수서류 '- 참여 신청서 1부' 는 무시하고 [서식 1] 을 고른다."""
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'{_p("모집공고")}'
        f'{_p("- 전문상담위원 참여 신청서 1부(서식 1)")}'
        f'{_p("[서식 1]")}'
        f'{_p("기업민원처리센터 전문상담위원 참여 신청서")}'
        "</hs:sec>"
    ).encode("utf-8")
    root = etree.fromstring(body)
    idx, marker = find_form_start_index(root)
    assert idx == 2
    assert marker == "[서식 1]"


def test_extract_forms_only_removes_notice(tmp_path: Path):
    src = tmp_path / "full.hwpx"
    out = tmp_path / "forms.hwpx"
    _make_hwpx(src, _section_with_notice_and_form())
    rep = extract_forms_only(src, out)
    assert rep.ok
    assert rep.marker == "[서식 1]"
    with zipfile.ZipFile(out) as z:
        text = z.read("Contents/section0.xml").decode("utf-8")
    assert "모집공고" not in text
    assert "수당지급" not in text
    assert "[서식 1]" in text
    assert "참여 신청서" in text
    assert not looks_like_notice_blob(text)


def test_extract_refuses_same_path(tmp_path: Path):
    src = tmp_path / "full.hwpx"
    _make_hwpx(src, _section_with_notice_and_form())
    import pytest

    with pytest.raises(ValueError, match="덮어쓰기"):
        extract_forms_only(src, src)
