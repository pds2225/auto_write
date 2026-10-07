# -*- coding: utf-8 -*-
"""hwpx_submission_cleanup 공통 후처리 검증."""
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from auto_write.services.hwpx_submission_cleanup import (
    finalize_submission_hwpx, reformat_bullet_heading, strip_meta_notes)

SRC = Path(r"C:\Users\ekth3\AppData\Local\Temp\claude\d--auto-write"
           r"\c99c8a8d-db7e-4688-ae3f-d3efb6b75b9d\scratchpad\STAR.hwpx")


def _ln(e):
    return etree.QName(e).localname


def _doc_text_and_colors(path):
    txt, bad_colors, lineseg = "", 0, 0
    with zipfile.ZipFile(path) as z:
        col = {}
        for n in z.namelist():
            if n.lower().endswith("header.xml"):
                for cp in etree.fromstring(z.read(n)).iter():
                    if _ln(cp) == "charPr":
                        col[cp.get("id")] = (cp.get("textColor") or "").upper().lstrip("#")
        for n in z.namelist():
            import re
            if re.search(r"Contents/section\d+\.xml$", n, re.I):
                root = etree.fromstring(z.read(n))
                txt += "".join(t.text or "" for t in root.iter() if _ln(t) == "t")
                lineseg += sum(1 for e in root.iter() if _ln(e) == "linesegarray")
                for r in root.iter():
                    if _ln(r) == "run":
                        c = col.get(r.get("charPrIDRef"), "")
                        if c and c not in ("000000", "FFFFFF"):
                            bad_colors += 1
    return txt, bad_colors, lineseg


@pytest.mark.skipif(not SRC.exists(), reason="STAR.hwpx 샘플 없음")
def test_finalize_removes_guides_colors_lineseg(tmp_path):
    out = tmp_path / "out.hwpx"
    stats = finalize_submission_hwpx(SRC, out)
    assert stats["guides_removed"] >= 1          # 작성방법 안내표 제거
    assert stats["charpr_blacked"] >= 1          # 유색 charPr 검정화
    txt, bad, lineseg = _doc_text_and_colors(out)
    assert "작성방법" not in txt                  # 안내문구 사라짐
    assert bad == 0                              # 비검정·비흰색 글자 0
    assert lineseg == 0                          # 줄위치 캐시 0


@pytest.mark.skipif(not SRC.exists(), reason="STAR.hwpx 샘플 없음")
def test_finalize_idempotent(tmp_path):
    a = tmp_path / "a.hwpx"
    b = tmp_path / "b.hwpx"
    finalize_submission_hwpx(SRC, a)
    stats2 = finalize_submission_hwpx(a, b)       # 두 번째 적용은 변화 0이어야(멱등)
    assert stats2["linesegarray_removed"] == 0
    assert stats2["guides_removed"] == 0
    assert stats2["charpr_blacked"] == 0
    assert stats2.get("spacing_clamped", 0) == 0


def test_finalize_rejects_inplace(tmp_path):
    p = tmp_path / "x.hwpx"
    p.write_bytes(b"PK\x03\x04")
    with pytest.raises(ValueError):
        finalize_submission_hwpx(p, p)            # 원본 덮어쓰기 금지


def _write_mini_hwpx(path: Path) -> None:
    """샌드박스용 최소 HWPX — 안내표·유색 charPr·linesegarray 포함."""
    ns = "http://www.hancom.co.kr/hwpml/2011/paragraph"
    header = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">
  <hh:charPr id="1" textColor="#000000">
    <hh:spacing hangul="-50" latin="-10"/>
  </hh:charPr>
  <hh:charPr id="2" textColor="#FF0000"/>
  <hh:charPr id="3" textColor="#FFFFFF"/>
</hh:head>
""".encode("utf-8")
    section = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hp="{ns}" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">
  <hp:tbl>
    <hp:tr><hp:tc><hp:subList><hp:p>
      <hp:run charPrIDRef="2"><hp:t>작성방법 ※삭제 후 제출</hp:t></hp:run>
    </hp:p></hp:subList></hp:tc></hp:tr>
  </hp:tbl>
  <hp:p>
    <hp:run charPrIDRef="1"><hp:t>본문 유지</hp:t></hp:run>
    <hp:linesegarray><hp:lineseg/></hp:linesegarray>
  </hp:p>
</hs:sec>
""".encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", b"application/hwp+zip")
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section)


def test_finalize_mini_hwpx_removes_guides_colors_lineseg(tmp_path):
    src = tmp_path / "in.hwpx"
    out = tmp_path / "out.hwpx"
    _write_mini_hwpx(src)
    stats = finalize_submission_hwpx(src, out)
    assert stats["guides_removed"] >= 1
    assert stats["charpr_blacked"] >= 1
    assert stats["linesegarray_removed"] >= 1
    assert stats["spacing_clamped"] >= 1
    txt, bad, lineseg = _doc_text_and_colors(out)
    assert "작성방법" not in txt
    assert "본문 유지" in txt
    assert bad == 0
    assert lineseg == 0
    # 원본 미수정
    assert src.read_bytes() != out.read_bytes()


def test_heading_reformat():
    assert reformat_bullet_heading("■ 외적 동기 — 지도는 길을...") == "■ (외적 동기)"
    assert reformat_bullet_heading("■ 항공우주 기술 차별화(주축)") == "■ (항공우주 기술 차별화)"
    assert reformat_bullet_heading("■ 기대 효과") == "■ (기대 효과)"
    assert reformat_bullet_heading("일반 문장") == "일반 문장"   # ■ 아니면 그대로


def test_strip_meta_notes():
    s = "실제 내용.\n※ 작성 안내 줄.\n다음(과장하지 않음) 내용."
    out = strip_meta_notes(s)
    assert "※" not in out
    assert "과장하지" not in out
    assert "실제 내용." in out and "다음" in out
