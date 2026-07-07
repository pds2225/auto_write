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


# --------------------------------------------------------------------------- #
# linesegarray 글씨 겹침 방지 — 채운 셀의 옛 줄위치 캐시 제거 회귀
# (사용자 실측: STAR·서울 AI 허브 신청서에서 값만 바꾸고 캐시를 안 지워 글씨 겹침 재발)
# --------------------------------------------------------------------------- #


def _section_xml_with_lineseg() -> bytes:
    """빈 값칸(상호) + 문단·값칸에 hp:linesegarray(옛 줄위치 캐시)를 가진 섹션."""
    label = (
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p>'
        '<hp:run charPrIDRef="0"><hp:t>상호</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
    )
    value = (
        '<hp:tc><hp:cellAddr colAddr="1" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="120"/></hp:linesegarray>'
        '<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p></hp:subList></hp:tc>'
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:linesegarray><hp:lineseg textpos="0" vertpos="0"/></hp:linesegarray>'
        '<hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="1" colCnt="2"><hp:tr>{label}{value}</hp:tr></hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    )
    return body.encode("utf-8")


def _make_hwpx_ls(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _HEADER_XML)
        z.writestr("Contents/section0.xml", _section_xml_with_lineseg())


def _count_lineseg(path: Path) -> int:
    from lxml import etree

    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    return sum(
        1 for el in root.iter() if etree.QName(el).localname == "linesegarray"
    )


def test_strip_linesegarray_when_filled(tmp_path):
    """채우면 옛 줄위치 캐시(linesegarray)가 전량 제거돼 한글 글씨 겹침을 막는다."""
    src = tmp_path / "ls.hwpx"
    _make_hwpx_ls(src)
    assert _count_lineseg(src) == 2  # 채우기 전: 문단1 + 값칸1
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"상호": "도보내비"})
    assert rep.filled.get("상호") == "도보내비"
    assert _cell_value(out, "상호") == "도보내비"  # 값 채워짐(내용 보존)
    assert _count_lineseg(out) == 0  # 캐시 전량 제거(겹침 방지)


def test_linesegarray_kept_when_no_change(tmp_path):
    """채울 게 없으면 재직렬화 없이 원본 그대로 — linesegarray 보존(불필요 변형 회피)."""
    src = tmp_path / "ls.hwpx"
    _make_hwpx_ls(src)
    out = tmp_path / "out.hwpx"
    fill_hwpx(src, out, identity={"존재하지않는라벨": "x"})
    assert _count_lineseg(out) == 2  # 무변경 → 원본 캐시 유지


def test_strip_linesegarray_helper_idempotent():
    """_strip_linesegarray: 제거 후 재호출은 0(멱등), 텍스트 내용 무손실."""
    from lxml import etree

    root = etree.fromstring(_section_xml_with_lineseg())
    assert hwpx_fill._strip_linesegarray(root) == 2
    assert hwpx_fill._strip_linesegarray(root) == 0  # 멱등
    texts = [t.text for t in root.iter(f"{{{_HP}}}t")]
    assert "상호" in texts  # 라벨 텍스트 보존


# --------------------------------------------------------------------------- #
# 구조 (a): 한 셀 '안' 인라인 빈칸(`라벨 : ______`) 채움 — offset 스플라이스
# (가시 빈칸만 채움 · used_keys 공유 · 형제 run 보존 · cross-run 은 보수적 skip)
# --------------------------------------------------------------------------- #


def _read_cell_runs_by_col(path: Path, col: int) -> list[tuple[str, str]]:
    """colAddr==col 셀의 run 목록을 (charPrIDRef, 직계 hp:t 결합 텍스트)로 반환."""
    from lxml import etree

    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    q = lambda t: f"{{{_HP}}}{t}"  # noqa: E731
    for tc in root.iter(q("tc")):
        ca = next((c for c in tc if c.tag == q("cellAddr")), None)
        if ca is not None and ca.get("colAddr") == str(col):
            runs = []
            for run in tc.iter(q("run")):
                txt = "".join(t.text or "" for t in run if t.tag == q("t"))
                runs.append((run.get("charPrIDRef"), txt))
            return runs
    return []


def test_inline_cell_single_field(tmp_path):
    """한 셀 안 `신청기업명 : ______` — 밑줄 자리만 값으로, 라벨·콜론 보존."""
    src = tmp_path / "inline1.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "신청기업명 : ______")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "도보네비(주)"})
    txt = _read_cell_by_col(out, 0)
    assert "도보네비(주)" in txt
    assert "______" not in txt
    assert txt.startswith("신청기업명 :")       # 라벨 보존
    assert rep.filled.get("기업명") == "도보네비(주)"
    assert rep.filled_count == 1


def test_inline_cell_multi_field(tmp_path):
    """한 문단 멀티필드 — 각 자리에 각 값, 서로 안 섞이고 라벨 둘 다 보존."""
    src = tmp_path / "inline2.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "신청기업명 : ______  대표자 : ____")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "A(주)", "대표자": "홍길동"})
    txt = _read_cell_by_col(out, 0)
    assert "A(주)" in txt and "홍길동" in txt
    assert "_" not in txt                        # 밑줄 전부 값으로 교체
    assert txt.startswith("신청기업명 :")
    # 값이 제 라벨 자리에: 기업명 값 < 대표자 라벨 < 대표자 값 순서
    assert txt.index("A(주)") < txt.index("대표자") < txt.index("홍길동")
    assert rep.filled_count == 2


def test_inline_colon_space_only_not_filled(tmp_path):
    """`비고 : `(콜론+공백만, 가시 빈칸 없음)는 옆 값칸과 모호 → 안 채운다."""
    src = tmp_path / "inline3.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "비고 : ")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"비고": "채우면안됨"})
    assert "채우면안됨" not in _read_cell_by_col(out, 0)
    assert rep.filled_count == 0
    assert "비고" in rep.residual               # 못 채웠으니 정직 보고


def test_inline_shares_used_keys_no_double_fill(tmp_path):
    """같은 라벨이 표 값칸 + 인라인 둘 다 있으면 한 번만 채움(이중기입 금지)."""
    src = tmp_path / "inline4.hwpx"
    _make_hwpx_cells(src, [
        _cellx(0, "신청기업명"),
        _cellx(1, ""),
        _cellx(2, "신청기업명 : ______"),
    ])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "한번만(주)"})
    assert _read_cell_by_col(out, 1) == "한번만(주)"   # 표 경로가 먼저 채움
    inline = _read_cell_by_col(out, 2)
    assert "한번만(주)" not in inline                  # 인라인 재채움 없음
    assert "______" in inline                          # 인라인 빈칸 그대로
    assert rep.filled_count == 1


def test_inline_sibling_run_preserved(tmp_path):
    """인라인 필드 앞뒤 형제 run 의 텍스트·charPrIDRef 가 불변."""
    tc = (
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p>'
        '<hp:run charPrIDRef="7"><hp:t>비고 : 참고내용</hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>  신청기업명 : ______</hp:t></hp:run>'
        '<hp:run charPrIDRef="9"><hp:t>  ※주의</hp:t></hp:run>'
        "</hp:p></hp:subList></hp:tc>"
    )
    src = tmp_path / "inline5.hwpx"
    _make_hwpx_cells(src, [tc])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "보존(주)"})
    runs = _read_cell_runs_by_col(out, 0)
    assert runs[0] == ("7", "비고 : 참고내용")   # 앞 형제 run 불변
    assert runs[2] == ("9", "  ※주의")           # 뒤 형제 run 불변
    assert runs[1][0] == "0"                      # 대상 run 서식 참조 불변
    assert "보존(주)" in runs[1][1] and "______" not in runs[1][1]
    assert rep.filled_count == 1


def test_inline_cross_run_span_skipped(tmp_path):
    """밑줄이 두 hp:t 로 쪼개지면(cross-run span) 채우지 않는다(오채움<빈칸)."""
    tc = (
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p>'
        '<hp:run charPrIDRef="0"><hp:t>신청기업명 : ___</hp:t></hp:run>'
        '<hp:run charPrIDRef="1"><hp:t>___</hp:t></hp:run>'
        "</hp:p></hp:subList></hp:tc>"
    )
    src = tmp_path / "inline6.hwpx"
    _make_hwpx_cells(src, [tc])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "안채움(주)"})
    txt = _read_cell_by_col(out, 0)
    assert "안채움(주)" not in txt
    assert "______" in txt                       # 빈칸 그대로(미채움)
    assert rep.filled_count == 0
    assert "기업명" in rep.residual              # 정직 보고


# --------------------------------------------------------------------------- #
# 구조 (d): 체크박스(□→■) 자동 체크 — 정확일치·모호스킵·used_keys 공유
# --------------------------------------------------------------------------- #


def test_checkbox_left_label_marks_option(tmp_path):
    """행 [라벨 | □옵션들] — 왼쪽 셀 라벨로 매칭해 값 옵션의 □ 만 ■ 로."""
    src = tmp_path / "cb1.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "사업자형태"), _cellx(1, "□개인 □법인")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "개인"})
    assert _read_cell_by_col(out, 1) == "■개인 □법인"
    assert rep.filled.get("사업자형태") == "개인"
    assert rep.filled_count == 1
    assert "사업자형태" not in rep.residual


def test_checkbox_inline_label_marks_option(tmp_path):
    """한 셀 '사업자형태 □개인 □법인' — 첫 □ 앞 텍스트가 인라인 라벨."""
    src = tmp_path / "cb2.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "사업자형태 □개인 □법인")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "개인"})
    assert _read_cell_by_col(out, 0) == "사업자형태 ■개인 □법인"
    assert rep.filled.get("사업자형태") == "개인"
    assert rep.filled_count == 1


def test_checkbox_exact_match_no_substring(tmp_path):
    """'개인정보' 값이 '개인' 옵션을 부분문자열로 오체크하면 안 된다(정확일치만)."""
    src = tmp_path / "cb3.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "사업자형태"), _cellx(1, "□개인 □법인")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "개인정보"})
    txt = _read_cell_by_col(out, 1)
    assert txt == "□개인 □법인"                # 아무것도 체크 안 됨
    assert "■" not in txt
    assert rep.filled_count == 0
    assert "사업자형태" in rep.residual         # 정직 보고


def test_checkbox_no_match_preserves_all(tmp_path):
    """값이 어느 옵션과도 일치하지 않으면 모든 □ 보존(날조 0)."""
    src = tmp_path / "cb4.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "사업자형태"), _cellx(1, "□개인 □법인")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "협동조합"})
    txt = _read_cell_by_col(out, 1)
    assert txt.count("□") == 2 and "■" not in txt
    assert rep.filled_count == 0


def test_checkbox_other_options_preserved(tmp_path):
    """'법인' 체크 시 '개인' 의 □ 는 그대로 — 매칭된 한 글자만 ■."""
    src = tmp_path / "cb5.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "사업자형태"), _cellx(1, "□개인 □법인")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "법인"})
    txt = _read_cell_by_col(out, 1)
    assert txt == "□개인 ■법인"
    assert txt.count("□") == 1 and txt.count("■") == 1
    assert rep.filled_count == 1


def test_checkbox_ambiguous_skipped(tmp_path):
    """값이 옵션 2개와 매칭(모호)이면 아무 박스도 안 건드림(오체크<빈칸)."""
    src = tmp_path / "cb6.hwpx"
    _make_hwpx_cells(src, [_cellx(0, "동의여부"), _cellx(1, "□예 □예")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"동의여부": "예"})
    txt = _read_cell_by_col(out, 1)
    assert txt.count("□") == 2 and "■" not in txt
    assert rep.filled_count == 0
    assert "동의여부" in rep.residual


def test_checkbox_shares_used_keys(tmp_path):
    """같은 라벨이 값칸+체크박스 둘 다면 한 번만 처리(used_keys 공유·이중 금지)."""
    src = tmp_path / "cb7.hwpx"
    _make_hwpx_cells(src, [
        _cellx(0, "사업자형태"),
        _cellx(1, ""),
        _cellx(2, "사업자형태 □개인 □법인"),
    ])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "개인"})
    assert _read_cell_by_col(out, 1) == "개인"     # 표 값칸 경로가 먼저 채움
    cb = _read_cell_by_col(out, 2)
    assert "■" not in cb and "□개인" in cb         # 체크박스 재처리 없음
    assert rep.filled_count == 1


def test_checkbox_trailing_punct_option_matched(tmp_path):
    """실측(008 서식): 옵션 꼬리 구두점 — `□ 자가(소유자   ),` 이 값 `자가` 와 일치.

    `_key` 정규화 후에도 꼬리 콤마가 남아(`자가,`) 정확일치가 실패하던 갭.
    꼬리 구두점(,.;:·)을 벗긴 뒤 정확일치해야 한다.
    """
    src = tmp_path / "cb8.hwpx"
    _make_hwpx_cells(src, [
        _cellx(0, "사업장구분"),
        _cellx(1, "□ 자가(소유자   ),  □ 임차(전세, 월세)"),
    ])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업장구분": "자가"})
    txt = _read_cell_by_col(out, 1)
    assert txt == "■ 자가(소유자   ),  □ 임차(전세, 월세)"   # ■ 1개·나머지 보존
    assert rep.filled.get("사업장구분") == "자가"
    assert rep.filled_count == 1
    assert "사업장구분" not in rep.residual


def test_checkbox_trailing_punct_still_no_substring(tmp_path):
    """꼬리 구두점 제거가 부분문자열 매칭을 부활시키면 안 된다.

    옵션 `개인정보보호,` → rstrip 후 `개인정보보호` ≠ 값 `개인` → 체크 금지.
    """
    src = tmp_path / "cb9.hwpx"
    _make_hwpx_cells(src, [
        _cellx(0, "사업자형태"),
        _cellx(1, "□개인정보보호, □법인"),
    ])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"사업자형태": "개인"})
    txt = _read_cell_by_col(out, 1)
    assert txt.count("□") == 2 and "■" not in txt   # 아무것도 체크 안 됨
    assert rep.filled_count == 0
    assert "사업자형태" in rep.residual              # 정직 보고


# --------------------------------------------------------------------------- #
# 구조 (b): 표 '밖' 본문 단락 인라인 빈칸(`라벨 : ______`) 채움 — 1.5 와 동일 커널
# (hs:sec 직계 hp:p 만 · 가시 빈칸만 · used_keys 공유 · 형제 run 보존 · 산문 보호)
# --------------------------------------------------------------------------- #


def _body_para(text: str, charpr: str = "0") -> str:
    """표 밖 본문 단락(hs:sec 직계 hp:p) 하나."""
    return (
        f'<hp:p><hp:run charPrIDRef="{charpr}"><hp:t>{text}</hp:t></hp:run></hp:p>'
    )


def _make_hwpx_body(
    path: Path, body_paras: list[str], cell_xmls: list[str] | None = None
) -> None:
    """본문 단락(표 밖 hp:p) + (선택) 단일행 표를 담은 최소 HWPX 픽스처."""
    tbl = ""
    if cell_xmls:
        row = f"<hp:tr>{''.join(cell_xmls)}</hp:tr>"
        tbl = (
            '<hp:p><hp:run charPrIDRef="0">'
            f'<hp:tbl rowCnt="1" colCnt="5">{row}</hp:tbl></hp:run></hp:p>'
        )
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f"{tbl}{''.join(body_paras)}</hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/section0.xml", section)


def _read_body_runs(path: Path) -> list[tuple[str, str]]:
    """hs:sec 직계 hp:p(표 run 제외)의 run 목록 (charPrIDRef, 직계 hp:t 결합 텍스트)."""
    from lxml import etree

    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    q = lambda t: f"{{{_HP}}}{t}"  # noqa: E731
    runs: list[tuple[str, str]] = []
    for p in root:
        if p.tag != q("p"):
            continue
        for run in p:
            if run.tag != q("run"):
                continue
            if any(c.tag == q("tbl") for c in run):
                continue  # 표를 품은 run 은 본문 텍스트 흐름이 아님
            txt = "".join(t.text or "" for t in run if t.tag == q("t"))
            runs.append((run.get("charPrIDRef"), txt))
    return runs


def _read_body_text(path: Path) -> str:
    return "".join(txt for _, txt in _read_body_runs(path))


def test_body_paragraph_visible_blank_filled(tmp_path):
    """본문 `신청인 성명 : ______` — 밑줄 자리에만 값, 라벨·콜론 보존(동의어 매칭)."""
    src = tmp_path / "body1.hwpx"
    _make_hwpx_body(src, [_body_para("신청인 성명 : ______")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"성명": "홍길동"})
    body = _read_body_text(out)
    assert "홍길동" in body
    assert "______" not in body
    assert body.startswith("신청인 성명 :")        # 라벨 보존
    assert rep.filled.get("성명") == "홍길동"
    assert rep.filled_count == 1


def test_body_colon_space_only_not_filled(tmp_path):
    """본문 `비고 : `(콜론+공백만, 가시 빈칸 없음) → 절대 안 채운다."""
    src = tmp_path / "body2.hwpx"
    _make_hwpx_body(src, [_body_para("비고 : ")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"비고": "채우면안됨"})
    assert "채우면안됨" not in _read_body_text(out)
    assert rep.filled_count == 0
    assert "비고" in rep.residual                  # 못 채웠으니 정직 보고


def test_body_sibling_run_preserved(tmp_path):
    """본문 필드 앞뒤 charPrIDRef 다른 형제 run 의 텍스트·속성 불변."""
    p = (
        "<hp:p>"
        '<hp:run charPrIDRef="7"><hp:t>비고 : 참고내용</hp:t></hp:run>'
        '<hp:run charPrIDRef="0"><hp:t>  신청인 성명 : ______</hp:t></hp:run>'
        '<hp:run charPrIDRef="9"><hp:t>  ※주의</hp:t></hp:run>'
        "</hp:p>"
    )
    src = tmp_path / "body3.hwpx"
    _make_hwpx_body(src, [p])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"성명": "홍길동"})
    runs = _read_body_runs(out)
    assert runs[0] == ("7", "비고 : 참고내용")     # 앞 형제 run 불변(산문값 보호 포함)
    assert runs[2] == ("9", "  ※주의")             # 뒤 형제 run 불변
    assert runs[1][0] == "0"                        # 대상 run 서식 참조 불변
    assert "홍길동" in runs[1][1] and "______" not in runs[1][1]
    assert rep.filled_count == 1


def test_body_shares_used_keys_with_table(tmp_path):
    """같은 라벨이 표 값칸 + 본문 둘 다 있으면 한 번만 채움(used_keys 공유)."""
    src = tmp_path / "body4.hwpx"
    _make_hwpx_body(
        src,
        [_body_para("신청기업명 : ______")],
        cell_xmls=[_cellx(0, "신청기업명"), _cellx(1, "")],
    )
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"기업명": "한번만(주)"})
    assert _read_cell_by_col(out, 1) == "한번만(주)"   # 표 경로가 먼저 채움
    body = _read_body_text(out)
    assert "한번만(주)" not in body                    # 본문 재채움 없음
    assert "______" in body                            # 본문 빈칸 그대로
    assert rep.filled_count == 1


def test_body_prose_colon_sentence_not_filled(tmp_path):
    """`주의 : 아래 사항을 확인하세요` 산문(값 자리에 실제 문장) → 절대 안 건드림."""
    src = tmp_path / "body5.hwpx"
    _make_hwpx_body(src, [_body_para("주의 : 아래 사항을 확인하세요")])
    out = tmp_path / "out.hwpx"
    rep = fill_hwpx(src, out, identity={"주의": "채우면안됨"})
    assert _read_body_text(out) == "주의 : 아래 사항을 확인하세요"  # 원문 그대로
    assert rep.filled_count == 0
    assert "주의" in rep.residual
