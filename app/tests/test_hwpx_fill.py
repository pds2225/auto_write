"""test_hwpx_fill.py — HWPX 직접 채우기(변환 왕복 없음) 검증.

실제 OWPML 구조(hp:tbl>hp:tr>hp:tc>subList>p>run>t)를 본뜬 최소 HWPX 픽스처로
다음을 증명한다: 값 입력·동의어/장식 라벨 매칭·플레이스홀더 교체·실값 덮어쓰기 금지·
날조0(잔여 정직 보고)·**양식 100% 보존**(섹션 외 ZIP 엔트리 바이트 동일)·원본 미수정.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path

import pytest

from auto_write.services import hwpx_fill
from auto_write.services.hwpx_fill import fill_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _cell(col: int, row: int, text: str) -> str:
    """OWPML 표 셀 한 칸(라벨/값). text='' 이면 빈 값 칸."""
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def _row(row: int, label: str, value: str) -> str:
    return f"<hp:tr>{_cell(0, row, label)}{_cell(1, row, value)}</hp:tr>"


def _section_xml() -> bytes:
    rows = "".join([
        _row(0, "상호", ""),                 # 동의어(기업명↔상호) + 빈칸
        _row(1, "○ 대표자", ""),             # 장식(글머리표) 라벨 + 빈칸
        _row(2, "사업자등록번호", "000-00-00000"),  # 플레이스홀더 → 교체
        _row(3, "주소", "서울특별시 강남구"),  # 실값 → 덮어쓰기 금지
        _row(4, "연락처", ""),               # identity 없음 → 빈칸 유지(날조0)
    ])
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="5" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p>"
        '<hp:p><hp:run charPrIDRef="0"><hp:t>표 밖 본문 EXAMPLE_TOKEN 입니다.</hp:t>'
        "</hp:run></hp:p>"
        "</hs:sec>"
    )
    return body.encode("utf-8")


# 섹션 외 '양식 자산'(보존돼야 하는 것들) — 일부러 식별 가능한 바이트.
_HEADER_XML = b'<?xml version="1.0"?><hh:head xmlns:hh="x">STYLE_FONTS_BORDERS</hh:head>'
_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"FAKE_IMAGE_DATA" * 20
_VERSION_XML = b'<?xml version="1.0"?><version>fixture</version>'
_CONTAINER_XML = b'<?xml version="1.0"?><container>fixture</container>'
_MIMETYPE = b"application/hwp+zip"


def _make_hwpx(path: Path) -> None:
    """최소 유효 HWPX(ZIP) 픽스처 작성: mimetype 선두+STORED, 표 1개, 이미지/헤더 포함."""
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("version.xml", _VERSION_XML)
        z.writestr("META-INF/container.xml", _CONTAINER_XML)
        z.writestr("Contents/header.xml", _HEADER_XML)
        z.writestr("Contents/section0.xml", _section_xml())
        z.writestr("BinData/image1.png", _IMAGE_BYTES)


@pytest.fixture()
def src_hwpx(tmp_path: Path) -> Path:
    p = tmp_path / "form.hwpx"
    _make_hwpx(p)
    return p


def _zip_entries(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist()}


def _cell_value(path: Path, label: str) -> str:
    """출력 HWPX 에서 라벨 행의 값 칸 텍스트를 읽어온다."""
    from lxml import etree

    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    q = lambda t: f"{{{_HP}}}{t}"  # noqa: E731
    for tr in root.iter(q("tr")):
        cells = [c for c in tr if c.tag == q("tc")]
        if len(cells) < 2:
            continue
        ltxt = "".join(t.text or "" for t in cells[0].iter(q("t"))).strip()
        if ltxt.replace("○", "").replace(" ", "") == label.replace("○", "").replace(" ", ""):
            return "".join(t.text or "" for t in cells[1].iter(q("t"))).strip()
    return "<not found>"


# --------------------------------------------------------------------------- #


def test_fills_empty_and_synonym_and_decorated_labels(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(
        src_hwpx, out,
        identity={"기업명": "도보네비게이션(주)", "대표자": "홍길동"},
    )
    assert rep.ok
    # 동의어: 기업명 → 상호 칸
    assert _cell_value(out, "상호") == "도보네비게이션(주)"
    # 장식 라벨: ○ 대표자
    assert _cell_value(out, "대표자") == "홍길동"
    assert rep.filled_count == 2


def test_placeholder_overwritten_but_real_value_protected(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(
        src_hwpx, out,
        identity={"사업자등록번호": "327-29-01754", "주소": "부산광역시 해운대구"},
    )
    # 플레이스홀더(000-00-00000)는 실번호로 교체
    assert _cell_value(out, "사업자등록번호") == "327-29-01754"
    # 실값(서울특별시 강남구)은 절대 덮어쓰지 않음
    assert _cell_value(out, "주소") == "서울특별시 강남구"
    assert "주소" in rep.residual          # 덮지 못했으니 정직하게 잔여 보고
    assert "사업자등록번호" not in rep.residual


def test_fabrication_zero_and_residual(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(
        src_hwpx, out,
        identity={"기업명": "테스트(주)", "없는라벨": "값있음"},
    )
    # identity 에 없는 연락처는 빈칸 유지(날조 0)
    assert _cell_value(out, "연락처") == ""
    # 양식에 없는 라벨은 잔여로 정직 보고
    assert "없는라벨" in rep.residual


def test_empty_value_never_written(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src_hwpx, out, identity={"기업명": "", "대표자": "  "})
    # 빈/공백 값은 채우지 않는다(날조 0)
    assert rep.filled_count == 0
    assert _cell_value(out, "상호") == ""


def test_form_preserved_nonsection_bytes_identical(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    fill_hwpx(src_hwpx, out, identity={"기업명": "보존테스트(주)"})
    src_e = _zip_entries(src_hwpx)
    out_e = _zip_entries(out)
    # 섹션 외 모든 엔트리(헤더 서식·이미지·버전·mimetype)는 내용 동일 = 양식 보존
    for name in ("mimetype", "version.xml", "META-INF/container.xml",
                 "Contents/header.xml", "BinData/image1.png"):
        assert out_e[name] == src_e[name], f"{name} 변경됨(양식 훼손)"
    # 섹션 XML 은 바뀌어야 함(값이 들어갔으니)
    assert out_e["Contents/section0.xml"] != src_e["Contents/section0.xml"]


def test_mimetype_first_and_stored(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    fill_hwpx(src_hwpx, out, identity={"기업명": "x(주)"})
    with zipfile.ZipFile(out) as z:
        infos = z.infolist()
    assert infos[0].filename == "mimetype"                 # 선두
    assert infos[0].compress_type == zipfile.ZIP_STORED    # 무압축


def test_original_file_untouched(src_hwpx, tmp_path):
    before = hashlib.sha256(src_hwpx.read_bytes()).hexdigest()
    out = tmp_path / "out.hwpx"
    fill_hwpx(src_hwpx, out, identity={"기업명": "x(주)", "대표자": "김철수"})
    after = hashlib.sha256(src_hwpx.read_bytes()).hexdigest()
    assert before == after, "원본이 수정됨"


def test_output_is_valid_zip_and_reparses(src_hwpx, tmp_path):
    from lxml import etree

    out = tmp_path / "out.hwpx"
    fill_hwpx(src_hwpx, out, identity={"기업명": "유효성(주)"})
    assert zipfile.is_zipfile(out)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        root = etree.fromstring(z.read("Contents/section0.xml"))  # 재파싱 OK
    assert root is not None


def test_idempotent(src_hwpx, tmp_path):
    out1 = tmp_path / "o1.hwpx"
    out2 = tmp_path / "o2.hwpx"
    ident = {"기업명": "멱등(주)", "대표자": "이영희"}
    fill_hwpx(src_hwpx, out1, identity=ident)
    # out1 을 다시 입력으로 채워도 같은 값(이미 채워진 칸은 덮지 않음)
    fill_hwpx(out1, out2, identity=ident)
    assert _cell_value(out1, "상호") == _cell_value(out2, "상호") == "멱등(주)"
    assert _cell_value(out1, "대표자") == _cell_value(out2, "대표자") == "이영희"


def test_direct_replacements(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src_hwpx, out, replacements={"EXAMPLE_TOKEN": "실제내용"})
    assert rep.replaced >= 1
    with zipfile.ZipFile(out) as z:
        body = z.read("Contents/section0.xml").decode("utf-8")
    assert "실제내용" in body and "EXAMPLE_TOKEN" not in body


def test_out_equals_in_raises(src_hwpx):
    with pytest.raises(ValueError):
        fill_hwpx(src_hwpx, src_hwpx, identity={"기업명": "x"})


def test_rejects_non_hwpx(tmp_path):
    p = tmp_path / "x.docx"
    p.write_bytes(b"PK\x03\x04 not really")
    with pytest.raises(ValueError):
        fill_hwpx(p, tmp_path / "o.hwpx", identity={"a": "b"})


# --- 적대검증 반영 회귀(하드링크·병합셀·라벨가드·치환보호·원자성·CLI) --------- #


def test_hardlink_out_equals_in_raises(src_hwpx, tmp_path):
    """CRITICAL: out 이 in 의 하드링크면(다른 이름·같은 inode) 원본 훼손 차단."""
    link = tmp_path / "hardlink.hwpx"
    try:
        os.link(src_hwpx, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("이 파일시스템은 하드링크 미지원")
    with pytest.raises(ValueError):
        fill_hwpx(src_hwpx, link, identity={"기업명": "x(주)"})


# 임의 셀(colAddr/colSpan 제어)로 단일행 표 HWPX 생성 — 병합·다열 검증용.
def _cellx(col: int, text: str, colspan: int = 1) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="0"/>'
        f'<hp:cellSpan colSpan="{colspan}" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>{text}</hp:t>'
        f"</hp:run></hp:p></hp:subList></hp:tc>"
    )


def _make_hwpx_cells(path: Path, cell_xmls: list[str]) -> None:
    row = f"<hp:tr>{''.join(cell_xmls)}</hp:tr>"
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="5">{row}</hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/section0.xml", section)


def _read_cell_by_col(path: Path, col: int) -> str:
    from lxml import etree

    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    q = lambda t: f"{{{_HP}}}{t}"  # noqa: E731
    for tc in root.iter(q("tc")):
        ca = next((c for c in tc if c.tag == q("cellAddr")), None)
        if ca is not None and ca.get("colAddr") == str(col):
            return "".join(t.text or "" for t in tc.iter(q("t"))).strip()
    return "<not found>"


def test_cellADDR_gap_prevents_wrong_cell_fill(tmp_path):
    """HIGH: 값칸 위치(colAddr+colSpan)에 셀이 없으면(병합 갭) 엉뚱한 칸을 안 채운다.

    위치 인덱스(i+1)였다면 col2 의 '기존데이터'를 값칸으로 오인했을 상황.
    """
    src = tmp_path / "gap.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "연락처"), _cellx(2, "기존데이터")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"연락처": "010-1234-5678"})
    assert _read_cell_by_col(out, 2) == "기존데이터"   # 옆 칸 오염 없음
    assert "연락처" in rep.residual                     # 값칸 없어 못 채움 → 정직 보고
    assert rep.filled_count == 0


def test_value_cell_found_across_colspan(tmp_path):
    """병합된 값 칸(colSpan>1)도 colAddr 로 정확히 찾아 채운다."""
    src = tmp_path / "span.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "기업명", colspan=1), _cellx(1, "", colspan=2)])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "스팬(주)"})
    assert _read_cell_by_col(out, 1) == "스팬(주)"
    assert rep.filled_count == 1


def test_label_target_never_overwritten(tmp_path):
    """MEDIUM: 값칸 후보가 또 다른 라벨이면 그 위에 값을 쓰지 않는다."""
    src = tmp_path / "ll.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "기업명"), _cellx(1, "대표자")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "x(주)"})
    assert _read_cell_by_col(out, 1) == "대표자"   # 라벨 보존
    assert "기업명" in rep.residual


def test_replacements_protect_real_value_and_label(src_hwpx, tmp_path):
    """MEDIUM: 직접 치환이 실값 칸·라벨 칸을 건드리지 않는다(보호)."""
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src_hwpx, out, replacements={"강남": "서초", "상호": "XXX"})
    # 실값 '서울특별시 강남구'(주소 칸) 보호 — '강남' 미치환
    assert _cell_value(out, "주소") == "서울특별시 강남구"
    # 라벨 '상호' 보호 — 치환 안 됨
    assert _cell_value(out, "상호") == ""
    assert rep.replaced == 0


def test_atomic_write_preserves_prior_output_on_failure(src_hwpx, tmp_path, monkeypatch):
    """MEDIUM: 쓰기 중 실패해도 기존 출력 파일이 손상·소실되지 않는다(원자적)."""
    out = tmp_path / "out.hwpx"
    out.write_bytes(b"PRECIOUS-PRIOR-OUTPUT")

    def _boom(*a, **k):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(hwpx_fill.os, "replace", _boom)
    with pytest.raises(OSError):
        fill_hwpx(src_hwpx, out, identity={"기업명": "x(주)"})
    assert out.read_bytes() == b"PRECIOUS-PRIOR-OUTPUT"     # 직전 출력 보존
    assert not list(tmp_path.glob("*.tmp"))                  # 임시파일 정리됨


def test_no_tmp_leftover_on_success(src_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    fill_hwpx(src_hwpx, out, identity={"기업명": "x(주)"})
    assert not list(tmp_path.glob("*.tmp"))


def test_standalone_declaration_preserved(tmp_path):
    """LOW: 원본 섹션 선언의 standalone='no' 가 보존된다."""
    src = tmp_path / "sa.hwpx"
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="2">'
        f'<hp:tr>{_cellx(0, "기업명")}{_cellx(1, "")}</hp:tr>'
        "</hp:tbl></hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/section0.xml", section)
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity={"기업명": "x(주)"})
    with zipfile.ZipFile(out) as z:
        head = z.read("Contents/section0.xml")[:80]
    assert b"standalone='no'" in head or b'standalone="no"' in head


def test_cli_returns_2_on_bad_input(tmp_path):
    """MEDIUM: CLI 가 잘못된 입력에 크래시 대신 종료코드 2 를 낸다."""
    from hwp_fill_direct import main

    bad = tmp_path / "bad.hwpx"
    bad.write_bytes(b"not a zip at all")
    rc = main([str(bad), "-o", str(tmp_path / "o.hwpx"), "--set", "기업명=x"])
    assert rc == 2
