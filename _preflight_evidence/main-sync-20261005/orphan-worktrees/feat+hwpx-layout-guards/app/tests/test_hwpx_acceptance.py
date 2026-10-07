"""test_hwpx_acceptance.py — HWPX 직접 수용검사 게이트 검증(변환 없이 XML 단 점검).

최소 OWPML/HWPX(zip) 픽스처로 세 결함(유색 텍스트·양식 안내문구·linesegarray)을
각각 검출하고, 클린 문서는 통과(ok)함을 증명한다. 읽기전용(원본 미수정) 도 확인한다.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from auto_write.services.hwpx_acceptance import (
    HwpxAcceptanceReport,
    run_hwpx_acceptance,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_MIMETYPE = b"application/hwp+zip"


# --------------------------------------------------------------------------- #
# 픽스처 빌더
# --------------------------------------------------------------------------- #


def _header_xml(char_prs: str) -> bytes:
    """header.xml — charPr 목록을 받아 최소 head 문서로 감싼다."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties>'
        f"{char_prs}"
        "</hh:charProperties></hh:refList></hh:head>"
    ).encode("utf-8")


def _charpr(idx: int, color: str | None) -> str:
    attr = f' textColor="{color}"' if color is not None else ""
    return f'<hh:charPr id="{idx}"{attr}/>'


def _p(text: str, *, lineseg: bool = False) -> str:
    """본문 단락(hp:p). lineseg=True 면 linesegarray(줄위치 캐시)를 포함."""
    ls = "<hp:linesegarray><hp:lineseg textpos=\"0\"/></hp:linesegarray>" if lineseg else ""
    return (
        f"<hp:p>{ls}<hp:run charPrIDRef=\"0\"><hp:t>{text}</hp:t></hp:run></hp:p>"
    )


def _cell(text: str) -> str:
    return (
        "<hp:tc><hp:cellAddr colAddr=\"0\" rowAddr=\"0\"/>"
        "<hp:cellSpan colSpan=\"1\" rowSpan=\"1\"/>"
        f"<hp:subList>{_p(text)}</hp:subList></hp:tc>"
    )


def _table(*cell_texts: str) -> str:
    cells = "".join(_cell(t) for t in cell_texts)
    return f'<hp:tbl rowCnt="1" colCnt="{len(cell_texts)}"><hp:tr>{cells}</hp:tr></hp:tbl>'


def _section_xml(body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">{body}</hs:sec>'
    ).encode("utf-8")


def _make_hwpx(path: Path, *, header: bytes | None = None,
               section: bytes | None = None) -> None:
    """최소 유효 HWPX(zip): mimetype 선두+STORED, header/section 선택."""
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("version.xml", b'<?xml version="1.0"?><v/>')
        if header is not None:
            z.writestr("Contents/header.xml", header)
        if section is not None:
            z.writestr("Contents/section0.xml", section)


# --- 대표 픽스처 ----------------------------------------------------------- #

# 안내문구 표: 핵심('작성방법') + 보조('삭제 후 제출','도식화') 동시 충족.
_GUIDE_CELL = "작성방법: 아래 표를 도식화하여 작성 후 삭제 후 제출하세요."
# 안내문구 단락(표 밖): 핵심('작성요령') + 보조('유의사항').
_GUIDE_PARA = "작성요령 ※ 유의사항 : 제출 전 반드시 확인"


@pytest.fixture()
def clean_hwpx(tmp_path: Path) -> Path:
    """결함 없는 HWPX — 검정/흰 charPr, 안내문구·linesegarray 없음."""
    p = tmp_path / "clean.hwpx"
    header = _header_xml(_charpr(0, "#000000") + _charpr(1, "#FFFFFF") + _charpr(2, None))
    section = _section_xml(_p("정상 본문입니다.") + _table("항목", "값"))
    _make_hwpx(p, header=header, section=section)
    return p


# --------------------------------------------------------------------------- #
# 클린 통과
# --------------------------------------------------------------------------- #


def test_clean_document_passes(clean_hwpx):
    rep = run_hwpx_acceptance(clean_hwpx)
    assert isinstance(rep, HwpxAcceptanceReport)
    assert rep.colored == 0
    assert rep.guides == 0
    assert rep.linesegarray == 0
    assert rep.ok is True
    assert rep.fail_defects == 0


def test_none_and_missing_textcolor_not_counted(clean_hwpx):
    """textColor 미지정·auto·none 은 기본색 → 유색으로 세지 않는다(오탐 0)."""
    rep = run_hwpx_acceptance(clean_hwpx)
    assert rep.colored == 0


# --------------------------------------------------------------------------- #
# ① 유색 텍스트
# --------------------------------------------------------------------------- #


def test_colored_textcolor_detected(tmp_path):
    p = tmp_path / "colored.hwpx"
    header = _header_xml(
        _charpr(0, "#000000") + _charpr(1, "#FF0000") + _charpr(2, "#808080")
    )
    _make_hwpx(p, header=header, section=_section_xml(_p("본문")))
    rep = run_hwpx_acceptance(p)
    assert rep.colored == 2           # 빨강·회색
    assert rep.ok is False
    assert any(s in ("#FF0000", "#808080") for s in rep.colored_samples)


def test_white_and_black_textcolor_not_counted(tmp_path):
    p = tmp_path / "wb.hwpx"
    header = _header_xml(_charpr(0, "#FFFFFF") + _charpr(1, "#000000") + _charpr(2, "000000"))
    _make_hwpx(p, header=header, section=_section_xml(_p("본문")))
    rep = run_hwpx_acceptance(p)
    assert rep.colored == 0
    assert rep.ok is True


def test_nonhex_textcolor_not_counted(tmp_path):
    """none/auto 같은 비-hex 값은 유색으로 오판하지 않는다."""
    p = tmp_path / "nonhex.hwpx"
    header = _header_xml(_charpr(0, "none") + _charpr(1, "auto"))
    _make_hwpx(p, header=header, section=_section_xml(_p("본문")))
    rep = run_hwpx_acceptance(p)
    assert rep.colored == 0


# --------------------------------------------------------------------------- #
# ② 양식 안내문구
# --------------------------------------------------------------------------- #


def test_guide_table_detected(tmp_path):
    p = tmp_path / "guide_tbl.hwpx"
    section = _section_xml(_p("실제 본문") + _table(_GUIDE_CELL))
    _make_hwpx(p, header=_header_xml(_charpr(0, "#000000")), section=section)
    rep = run_hwpx_acceptance(p)
    assert rep.guides == 1
    assert rep.ok is False


def test_guide_paragraph_detected(tmp_path):
    p = tmp_path / "guide_p.hwpx"
    section = _section_xml(_p(_GUIDE_PARA) + _p("정상 본문"))
    _make_hwpx(p, header=_header_xml(_charpr(0, "#000000")), section=section)
    rep = run_hwpx_acceptance(p)
    assert rep.guides == 1


def test_guide_paragraph_inside_guide_table_not_double_counted(tmp_path):
    """안내 표 안의 단락이 자체로 안내문구여도 이중 카운트하지 않는다(표에서 1회)."""
    p = tmp_path / "guide_nested.hwpx"
    # 셀 텍스트 자체가 핵심+보조를 모두 담아 표·단락 둘 다 매칭될 수 있는 상황.
    section = _section_xml(_table(_GUIDE_CELL))
    _make_hwpx(p, header=_header_xml(_charpr(0, "#000000")), section=section)
    rep = run_hwpx_acceptance(p)
    assert rep.guides == 1


def test_core_without_aux_not_guide(tmp_path):
    """핵심어만 있고 보조어가 없으면 안내문구로 세지 않는다."""
    p = tmp_path / "core_only.hwpx"
    section = _section_xml(_p("작성방법을 참고하여 자유롭게 기술"))
    _make_hwpx(p, header=_header_xml(_charpr(0, "#000000")), section=section)
    rep = run_hwpx_acceptance(p)
    assert rep.guides == 0


# --------------------------------------------------------------------------- #
# ③ linesegarray(겹침 위험)
# --------------------------------------------------------------------------- #


def test_linesegarray_detected(tmp_path):
    p = tmp_path / "lineseg.hwpx"
    section = _section_xml(
        _p("첫 줄", lineseg=True) + _p("둘째 줄", lineseg=True) + _p("셋째 줄")
    )
    _make_hwpx(p, header=_header_xml(_charpr(0, "#000000")), section=section)
    rep = run_hwpx_acceptance(p)
    assert rep.linesegarray == 2
    assert rep.ok is False


# --------------------------------------------------------------------------- #
# 결합 결함 + as_dict
# --------------------------------------------------------------------------- #


def test_all_defects_combined(tmp_path):
    p = tmp_path / "dirty.hwpx"
    header = _header_xml(_charpr(0, "#0000FF"))
    section = _section_xml(
        _p("본문", lineseg=True) + _p(_GUIDE_PARA) + _table(_GUIDE_CELL)
    )
    _make_hwpx(p, header=header, section=section)
    rep = run_hwpx_acceptance(p)
    assert rep.colored == 1
    assert rep.guides == 2            # 안내 표 1 + 표 밖 안내 단락 1
    assert rep.linesegarray == 1
    assert rep.fail_defects == 4
    assert rep.ok is False


def test_as_dict_shape(tmp_path):
    p = tmp_path / "d.hwpx"
    header = _header_xml(_charpr(0, "#FF0000"))
    _make_hwpx(p, header=header, section=_section_xml(_p("본문")))
    d = run_hwpx_acceptance(p).as_dict()
    for key in ("source", "ok", "verdict", "fail_defects",
                "colored", "guides", "linesegarray",
                "colored_samples", "guides_samples", "notes"):
        assert key in d
    assert d["ok"] is False
    assert d["colored"] == 1


# --------------------------------------------------------------------------- #
# 견고성 / 읽기전용
# --------------------------------------------------------------------------- #


def test_original_file_untouched(tmp_path):
    p = tmp_path / "ro.hwpx"
    header = _header_xml(_charpr(0, "#FF0000"))
    section = _section_xml(_p("본문", lineseg=True) + _table(_GUIDE_CELL))
    _make_hwpx(p, header=header, section=section)
    before = hashlib.sha256(p.read_bytes()).hexdigest()
    run_hwpx_acceptance(p)
    after = hashlib.sha256(p.read_bytes()).hexdigest()
    assert before == after, "원본이 수정됨(읽기전용 위반)"


def test_missing_header_and_section_notes(tmp_path):
    """header/section 이 없으면 크래시 대신 note 로 생략을 보고한다."""
    p = tmp_path / "empty.hwpx"
    _make_hwpx(p)   # mimetype·version 만
    rep = run_hwpx_acceptance(p)
    assert rep.ok is True
    assert rep.fail_defects == 0
    assert any("header.xml" in n for n in rep.notes)
    assert any("section" in n for n in rep.notes)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_hwpx_acceptance(tmp_path / "nope.hwpx")


def test_non_zip_raises(tmp_path):
    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"not a zip at all")
    with pytest.raises(ValueError):
        run_hwpx_acceptance(bad)


def test_bad_section_xml_skipped_with_note(tmp_path):
    """섹션 XML 이 깨져도 크래시하지 않고 note 로 건너뛴다."""
    p = tmp_path / "broken.hwpx"
    with zipfile.ZipFile(p, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(_charpr(0, "#000000")))
        z.writestr("Contents/section0.xml", b"<hs:sec>NOT CLOSED")
    rep = run_hwpx_acceptance(p)
    assert any("section0.xml" in n and "파싱 실패" in n for n in rep.notes)
