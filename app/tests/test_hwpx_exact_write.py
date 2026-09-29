# -*- coding: utf-8 -*-
"""P0-3: exact hp:t writes cancel the whole plan when any check fails."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from auto_write.services.hwpx_fill import ExactTextTarget, commit_exact_text_writes, fill_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _hwpx(path: Path, section: str, header: bytes = b"<hh:head>LOCKED</hh:head>") -> str:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, b"application/hwp+zip")
        archive.writestr("Contents/header.xml", header)
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("BinData/keep.bin", b"UNTOUCHED")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section() -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run>"
        "<hp:t>기업명 :</hp:t><hp:t></hp:t>"
        "</hp:run></hp:p>"
        "<hp:p><hp:run><hp:t>※ 안내문입니다</hp:t></hp:run></hp:p>"
        "</hs:sec>"
    )


def _texts(path: Path) -> list[str]:
    from lxml import etree
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("Contents/section0.xml"))
    found = []
    for node in root.iter(f"{{{_HP}}}t"):
        found.append(node.text or "")
    return found


def test_exact_write_changes_only_the_approved_text_node(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    sha = _hwpx(src, _section())
    before = src.read_bytes()
    header = zipfile.ZipFile(src).read("Contents/header.xml")
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "주식회사")],
        source_sha256=sha,
    )
    assert report.ok is True and report.cancelled is False
    assert src.read_bytes() == before
    assert _texts(dst) == ["기업명 :", "주식회사", "※ 안내문입니다"]
    with zipfile.ZipFile(dst) as archive:
        assert archive.read("Contents/header.xml") == header
        assert archive.read("BinData/keep.bin") == b"UNTOUCHED"


def test_any_failed_target_cancels_the_whole_plan(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    sha = _hwpx(src, _section())
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [
            ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "주식회사"),
            ExactTextTarget("Contents/section0.xml", 1, 0, 0, "다른글", "침범"),
        ],
        source_sha256=sha,
    )
    assert report.ok is False and report.cancelled is True
    assert report.reason.startswith("EXPECTED_TEXT_MISMATCH")
    assert not dst.exists()
    assert _texts(src)[1] == ""


def test_sha_mismatch_writes_nothing(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _hwpx(src, _section())
    dst = tmp_path / "out.hwpx"
    report = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "주식회사")],
        source_sha256="0" * 64,
    )
    assert report.reason == "SHA_MISMATCH"
    assert not dst.exists()


def test_existing_text_and_bad_coordinates_write_nothing(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    sha = _hwpx(src, _section())
    dst = tmp_path / "out.hwpx"
    blocked = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget("Contents/section0.xml", 1, 0, 0, "※ 안내문입니다", "침범")],
        source_sha256=sha,
    )
    assert blocked.ok is False and blocked.cancelled is True
    assert not dst.exists()
    assert blocked.reason.startswith("EXISTING_VALUE")
    mismatched = commit_exact_text_writes(
        src, dst,
        [ExactTextTarget("Contents/section0.xml", 0, 0, 1, "", "주식회사", table_index=9, row=0, col=1)],
        source_sha256=sha,
    )
    assert mismatched.ok is False and not dst.exists()
    assert mismatched.reason in {"COORDINATE_MISMATCH", "INDEX_INCOMPLETE"}


def test_legacy_fill_still_writes_an_empty_value_cell(tmp_path: Path) -> None:
    src = tmp_path / "legacy.hwpx"
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        "<hp:subList><hp:p><hp:run><hp:t>상호</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
        '<hp:tc><hp:cellAddr colAddr="1" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/>'
        "<hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList></hp:tc>"
        "</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>"
    )
    _hwpx(src, section)
    dst = tmp_path / "legacy-out.hwpx"
    report = fill_hwpx(src, dst, identity={"기업명": "도보네비"}, force_black=False)
    assert report.ok is True
    assert "상호" in report.filled or any("도보네비" in item for item in _texts(dst))
