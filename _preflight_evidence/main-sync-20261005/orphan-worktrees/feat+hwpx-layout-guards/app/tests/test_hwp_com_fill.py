"""test_hwp_com_fill.py — 바이너리 .hwp 한글 COM 직접 채우기 검증(mock COM).

한글이 없는 환경에서도 핵심 로직을 증명한다: 누름틀 필드명↔라벨 동의어 매칭·
PutFieldText 호출·날조0·잔여 정직보고·COM 미가용 시 정직 degradation·안전가드.
실제 한글 E2E 는 사용자 PC(대화형) 몫이다.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import pytest

from auto_write.services import hwp_com_fill
from auto_write.services.hwp_com_fill import (
    _parse_field_list,
    fill_hwp_com,
    fill_hwp_via_hwpx,
)


class _MockHwp:
    """한글 COM 객체 흉내 — PutFieldText 호출을 기록하고 SaveAs 로 파일을 만든다."""

    def __init__(self, fields: str):
        self._fields = fields
        self.put: dict[str, str] = {}
        self.saved_to: str | None = None
        self.save_ok = True

    def RegisterModule(self, *a):  # noqa: N802
        return True

    def SetMessageBoxMode(self, *a):  # noqa: N802
        return 0

    def Open(self, *a):  # noqa: N802
        return True

    def GetFieldList(self, *a):  # noqa: N802
        return self._fields

    def PutFieldText(self, name, val):  # noqa: N802
        self.put[name] = val

    def SaveAs(self, path, fmt, opt):  # noqa: N802
        if self.save_ok:
            Path(path).write_bytes(b"HWPDUMMY")
            self.saved_to = path
        return self.save_ok

    def Clear(self, *a):  # noqa: N802
        return True

    def Quit(self):  # noqa: N802
        return True


@pytest.fixture()
def src_hwp(tmp_path: Path) -> Path:
    p = tmp_path / "form.hwp"
    p.write_bytes(b"\xd0\xcf\x11\xe0 fake hwp")  # COM 은 mock 이라 내용 무관
    return p


def _install_com(monkeypatch, mock: _MockHwp):
    monkeypatch.setattr(hwp_com_fill, "hancom_com_available", lambda: True)
    monkeypatch.setattr(hwp_com_fill, "_dispatch_hwp", lambda: mock)


# --------------------------------------------------------------------------- #


def test_parse_field_list_strips_instance_suffix_and_dedup():
    raw = "기업명{{0}}\n대표자{{0}}\n기업명{{1}}\n\x02연락처"
    assert _parse_field_list(raw) == ["기업명", "대표자", "연락처"]
    assert _parse_field_list("") == []
    assert _parse_field_list(None) == []


def test_fills_matching_fields_with_synonym(monkeypatch, src_hwp, tmp_path):
    mock = _MockHwp("기업명\n대표자\n연락처")
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(
        src_hwp, out,
        identity={"기업명": "도보네비게이션(주)", "성명": "홍길동"},  # 성명↔대표자 동의어
    )
    assert rep.ok and rep.method == "hancom_com_field"
    assert mock.put == {"기업명": "도보네비게이션(주)", "대표자": "홍길동"}
    assert "연락처" not in mock.put          # identity 에 없음 → 미입력(날조0)
    assert rep.filled == {"기업명": "도보네비게이션(주)", "대표자": "홍길동"}


def test_residual_reported_for_unmatched_label(monkeypatch, src_hwp, tmp_path):
    mock = _MockHwp("기업명")
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "A", "없는필드": "값"})
    assert "없는필드" in rep.residual
    assert "기업명" not in rep.residual


def test_fabrication_zero_empty_value(monkeypatch, src_hwp, tmp_path):
    mock = _MockHwp("기업명\n대표자")
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "", "대표자": "  "})
    assert mock.put == {}                    # 빈/공백 값은 입력 안 함
    assert rep.filled == {}


def test_no_fields_note(monkeypatch, src_hwp, tmp_path):
    mock = _MockHwp("")                       # 누름틀 없는 양식
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "A"})
    assert rep.fields_found == []
    assert any("HWPX" in n for n in rep.notes)   # HWPX 경로 권유


def test_save_failure_reported(monkeypatch, src_hwp, tmp_path):
    mock = _MockHwp("기업명")
    mock.save_ok = False
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "A"})
    assert rep.ok is False
    assert any("저장 실패" in n for n in rep.notes)


def test_com_unavailable_honest_degradation(monkeypatch, src_hwp, tmp_path):
    monkeypatch.setattr(hwp_com_fill, "hancom_com_available", lambda: False)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "A"})
    assert rep.ok is False
    assert not out.exists()                   # 실패 시 가짜 출력 생성 안 함
    assert any("HWPX" in n for n in rep.notes)   # 대안 안내


def test_use_com_false_skips_dispatch(monkeypatch, src_hwp, tmp_path):
    def _boom():
        raise AssertionError("use_com=False 인데 COM 을 띄움")

    monkeypatch.setattr(hwp_com_fill, "hancom_com_available", lambda: True)
    monkeypatch.setattr(hwp_com_fill, "_dispatch_hwp", _boom)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "A"}, use_com=False)
    assert rep.ok is False


def test_out_equals_in_raises(src_hwp):
    with pytest.raises(ValueError):
        fill_hwp_com(src_hwp, src_hwp, identity={"기업명": "A"})


def test_rejects_unsupported_ext(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        fill_hwp_com(p, tmp_path / "o.hwp", identity={"a": "b"})


def test_copied_no_fields_when_no_match(monkeypatch, src_hwp, tmp_path):
    """LOW: 누름틀은 있으나 매칭 0개면 '필드 채움' 과대보고 대신 copied_no_fields."""
    mock = _MockHwp("기업명")
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"없는라벨": "값"})
    assert rep.ok is True                       # 저장 자체는 성공
    assert rep.filled == {}
    assert rep.method == "copied_no_fields"      # 거짓 '채움 성공' 아님
    assert any("원본 복사본" in n for n in rep.notes)


def test_residual_reports_duplicate_cluster_label(monkeypatch, src_hwp, tmp_path):
    """LOW: 같은 클러스터 라벨 2개인데 필드 1개면, 못 채운 쪽을 residual 로 정직 노출."""
    mock = _MockHwp("기업명")                     # 필드는 기업명 하나뿐
    _install_com(monkeypatch, mock)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_com(src_hwp, out, identity={"기업명": "A(주)", "상호": "B(주)"})
    assert mock.put == {"기업명": "A(주)"}         # 한 필드만 기입
    assert "상호" in rep.residual                 # 못 들어간 동의어 라벨 정직 보고


def test_hardlink_out_equals_in_raises(monkeypatch, src_hwp, tmp_path):
    link = tmp_path / "hardlink.hwp"
    try:
        os.link(src_hwp, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("이 파일시스템은 하드링크 미지원")
    with pytest.raises(ValueError):
        fill_hwp_com(src_hwp, link, identity={"기업명": "x"})


# --- 표 양식 자동 파이프라인(.hwp→hwpx→채움→.hwp) 검증 (mock COM 변환=무손실 복사) -- #

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _table_hwpx_bytes() -> bytes:
    def cell(col, text):
        return (
            f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="0"/>'
            f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
            f'<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>{text}</hp:t>'
            f"</hp:run></hp:p></hp:subList></hp:tc>"
        )

    rows = (
        f'<hp:tr>{cell(0, "기업명")}{cell(1, "")}</hp:tr>'
        f'<hp:tr>{cell(0, "대표자")}{cell(1, "")}</hp:tr>'
    )
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    return section


def _write_table_hwpx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, b"application/hwp+zip")
        z.writestr("Contents/header.xml", b"<head>STYLES</head>")
        z.writestr("Contents/section0.xml", _table_hwpx_bytes())


def _install_lossless_com(monkeypatch):
    """한글 COM 변환을 '무손실 복사'로 모킹(.hwp↔.hwpx 를 바이트 복사로 흉내)."""
    monkeypatch.setattr(hwp_com_fill, "hancom_com_available", lambda: True)
    monkeypatch.setattr(
        hwp_com_fill, "_convert_via_com",
        lambda src, dst, fmts: shutil.copyfile(str(src), str(dst)),
    )


def _read_cell_value(hwp_or_hwpx: Path, label: str) -> str:
    from lxml import etree

    with zipfile.ZipFile(hwp_or_hwpx) as z:
        root = etree.fromstring(z.read("Contents/section0.xml"))
    q = lambda t: f"{{{_HP}}}{t}"  # noqa: E731
    for tr in root.iter(q("tr")):
        cells = [c for c in tr if c.tag == q("tc")]
        if len(cells) < 2:
            continue
        ltxt = "".join(t.text or "" for t in cells[0].iter(q("t"))).strip()
        if ltxt == label:
            return "".join(t.text or "" for t in cells[1].iter(q("t"))).strip()
    return "<not found>"


@pytest.fixture()
def src_hwp_table(tmp_path: Path) -> Path:
    """표 양식 .hwp(내용은 HWPX 바이트 — mock 변환이 복사하므로 유효)."""
    p = tmp_path / "table_form.hwp"
    _write_table_hwpx(p)
    return p


def test_pipeline_fills_table_form_hwp(monkeypatch, src_hwp_table, tmp_path):
    """표 양식 .hwp 를 자동 파이프라인으로 채우고 .hwp 로 되돌린다(구조 보존)."""
    _install_lossless_com(monkeypatch)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_via_hwpx(
        src_hwp_table, out, identity={"기업명": "도보네비게이션(주)", "대표자": "홍길동"},
    )
    assert rep.ok and rep.method == "hwp_via_hwpx"
    assert rep.filled_count == 2
    assert _read_cell_value(out, "기업명") == "도보네비게이션(주)"
    assert _read_cell_value(out, "대표자") == "홍길동"
    assert rep.structure_preserved is True
    assert rep.counts["before"]["cells"] == rep.counts["after"]["cells"]


def test_pipeline_original_untouched(monkeypatch, src_hwp_table, tmp_path):
    import hashlib

    _install_lossless_com(monkeypatch)
    before = hashlib.sha256(src_hwp_table.read_bytes()).hexdigest()
    fill_hwp_via_hwpx(src_hwp_table, tmp_path / "out.hwp", identity={"기업명": "x(주)"})
    assert hashlib.sha256(src_hwp_table.read_bytes()).hexdigest() == before


def test_pipeline_com_unavailable_honest(monkeypatch, src_hwp_table, tmp_path):
    monkeypatch.setattr(hwp_com_fill, "hancom_com_available", lambda: False)
    out = tmp_path / "out.hwp"
    rep = fill_hwp_via_hwpx(src_hwp_table, out, identity={"기업명": "x(주)"})
    assert rep.ok is False
    assert not out.exists()
    assert any("COM" in n for n in rep.notes)


def test_pipeline_hwpx_to_hwpx_needs_no_com(monkeypatch, tmp_path):
    """입력·출력 모두 .hwpx 면 한글 없이도 동작(need_com=False)."""
    monkeypatch.setattr(hwp_com_fill, "hancom_com_available", lambda: False)
    src = tmp_path / "f.hwpx"
    _write_table_hwpx(src)
    out = tmp_path / "out.hwpx"
    rep = fill_hwp_via_hwpx(src, out, identity={"기업명": "노콤(주)"})
    assert rep.ok is True
    assert _read_cell_value(out, "기업명") == "노콤(주)"


def test_pipeline_out_equals_in_raises(src_hwp_table):
    with pytest.raises(ValueError):
        fill_hwp_via_hwpx(src_hwp_table, src_hwp_table, identity={"기업명": "x"})


def test_pipeline_no_tmp_leftover(monkeypatch, src_hwp_table, tmp_path):
    _install_lossless_com(monkeypatch)
    out = tmp_path / "out.hwp"
    fill_hwp_via_hwpx(src_hwp_table, out, identity={"기업명": "x(주)"})
    assert not list(tmp_path.glob("*.tmp*"))
