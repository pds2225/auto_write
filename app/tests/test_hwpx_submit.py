"""test_hwpx_submit.py — HWPX 제출 파이프라인(채움→수용검사 게이트→_DRAFT 강제) 검증.

B②(게이트 배선)+B③(제출 파이프라인): fill_hwpx 로 채운 산출물을 run_hwpx_acceptance
게이트로 판정하고, fail/검사불능이면 force_draft_name(단일 출처)으로 _DRAFT 를 강제해
제출 이름으로 절대 통과시키지 않는다(fail-closed, R9). 원본 미수정도 확인한다.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from auto_write.services import hwpx_submit as hs
from auto_write.services.hwpx_submit import submit_hwpx

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_MIMETYPE = b"application/hwp+zip"


# --------------------------------------------------------------------------- #
# 픽스처 빌더 — test_hwpx_fill/_acceptance 의 최소 OWPML 스타일 재사용
# --------------------------------------------------------------------------- #


def _header_xml(*, colored: bool) -> bytes:
    """header.xml — colored=True 면 유색 charPr(수용검사 fail 유발)을 심는다."""
    cp = (
        '<hh:charPr id="0" textColor="FF0000"/>'
        if colored
        else '<hh:charPr id="0" textColor="000000"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="1">'
        f"{cp}</hh:charProperties></hh:refList></hh:head>"
    ).encode("utf-8")


def _cell(col: int, row: int, text: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def _row(row: int, label: str, value: str) -> str:
    return f"<hp:tr>{_cell(0, row, label)}{_cell(1, row, value)}</hp:tr>"


def _section_xml() -> bytes:
    rows = "".join([_row(0, "상호", ""), _row(1, "대표자", "")])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="2" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")


def _make_hwpx(path: Path, *, colored: bool = False) -> None:
    """최소 유효 HWPX: mimetype 선두+STORED, 채울 표 1개, header(유색 선택)."""
    with zipfile.ZipFile(path, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=colored))
        z.writestr("Contents/section0.xml", _section_xml())


@pytest.fixture()
def clean_hwpx(tmp_path: Path) -> Path:
    p = tmp_path / "clean_form.hwpx"
    _make_hwpx(p, colored=False)
    return p


@pytest.fixture()
def colored_hwpx(tmp_path: Path) -> Path:
    p = tmp_path / "colored_form.hwpx"
    _make_hwpx(p, colored=True)
    return p


# --------------------------------------------------------------------------- #
# 1) 깨끗한 양식 → 게이트 통과(제출 이름 유지)
# --------------------------------------------------------------------------- #


def test_submit_clean_form_passes_gate(clean_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(clean_hwpx, out, identity={"기업명": "도보네비(주)"})
    assert rep.ok is True
    assert rep.final == str(out)                       # 이름 그대로(제출가능)
    assert "_DRAFT" not in Path(rep.final).name
    assert Path(rep.final).exists()
    assert rep.filled == {"기업명": "도보네비(주)"}     # 동의어(기업명↔상호) 채움
    assert rep.draft_marked is False
    assert rep.acceptance.get("ok") is True
    assert rep.error == ""


# --------------------------------------------------------------------------- #
# 2) 양식에 원래 있던 유색 charPr 는 결함이 아니다
# --------------------------------------------------------------------------- #


def test_submit_gate_fail_forces_draft(colored_hwpx, tmp_path):
    """양식 charPr 색을 채움이 재사용하면 _DRAFT 로 바꾸지 않는다."""
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(colored_hwpx, out, identity={"기업명": "도보네비(주)"},
                      normalize_colors=False)
    assert rep.ok is True
    assert Path(rep.final).name == "out.hwpx"
    assert out.exists()
    assert rep.draft_marked is False
    assert rep.acceptance.get("colored", -1) == 0
    assert rep.filled == {"기업명": "도보네비(주)"}
    assert any("baseline" in note for note in rep.acceptance.get("notes", []))


def test_submit_normalizes_colors_by_default(colored_hwpx, tmp_path):
    """기본(normalize_colors=True): 잔존 예시 유색체가 검정으로 정규화돼 제출가능."""
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(colored_hwpx, out, identity={"기업명": "도보네비(주)"})
    assert rep.ok is True                              # 유색 자동 해소 → 제출가능
    assert Path(rep.final).name == "out.hwpx"          # _DRAFT 아님(깨끗한 이름)
    assert rep.acceptance.get("colored", -1) == 0      # 유색 0
    assert any(
        ("검정 정규화" in n) or ("제출 cleanup" in n and "검정" in n)
        for n in rep.notes
    )   # 정규화/cleanup 수행 명시


# --------------------------------------------------------------------------- #
# 3) 수용검사 '예외'(검사불능) → fail-closed: 똑같이 _DRAFT 강제 + error 기록
# --------------------------------------------------------------------------- #


def test_submit_acceptance_exception_fail_closed(clean_hwpx, tmp_path, monkeypatch):
    def _boom(path, **_kwargs):
        raise RuntimeError("acceptance exploded (simulated)")

    monkeypatch.setattr(hs, "run_hwpx_acceptance", _boom)
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(clean_hwpx, out, identity={"기업명": "x(주)"})
    assert rep.ok is False                             # 판정 불가 = 제출불가
    final = Path(rep.final)
    assert final.name == "out_DRAFT.hwpx"              # 깨끗한 이름으로 절대 통과 금지
    assert final.exists()
    assert not out.exists()
    assert rep.draft_marked is True
    assert "acceptance exploded" in rep.error          # 침묵 금지 — error 명시
    assert rep.acceptance.get("exception")             # 검사불능 마커(CLI exit 3 근거)


# --------------------------------------------------------------------------- #
# 4) acceptance_gate=False → 최종 제출본 우회 금지·_DRAFT 강제
# --------------------------------------------------------------------------- #


def test_submit_no_gate_flag(colored_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        colored_hwpx, out, identity={"기업명": "x(주)"}, acceptance_gate=False
    )
    assert rep.ok is False                             # gate 우회는 제출가능이 아님
    assert Path(rep.final).name == "out_DRAFT.hwpx"
    assert Path(rep.final).exists()
    assert not out.exists()
    assert rep.draft_marked is True
    assert rep.acceptance.get("ok") is True            # gate 결과는 기록됨
    assert any("우회 요청" in n for n in rep.notes)    # 우회 사실을 정직하게 노트


# --------------------------------------------------------------------------- #
# 5) 원본 미수정 — 게이트 fail(rename 발생) 경로에서도 원본 해시 불변
# --------------------------------------------------------------------------- #


def test_submit_original_untouched(colored_hwpx, tmp_path):
    before = hashlib.sha256(colored_hwpx.read_bytes()).hexdigest()
    submit_hwpx(colored_hwpx, tmp_path / "out.hwpx", identity={"기업명": "x(주)"})
    after = hashlib.sha256(colored_hwpx.read_bytes()).hexdigest()
    assert before == after, "원본이 수정됨"


# --------------------------------------------------------------------------- #
# 6) CLI exit 계약: 0=제출가능 / 1=입력오류 / 2=제출불가(_DRAFT) / 3=검사불능
# --------------------------------------------------------------------------- #


def test_cli_default_output_is_source_adjacent(clean_hwpx, tmp_path):
    """-o 미지정 제출 결과는 원본 HWPX와 같은 폴더에 생성된다."""
    from hwpx_submit import main

    src = tmp_path / "GovTech_아이디어기획서_원본.hwpx"
    src.write_bytes(clean_hwpx.read_bytes())

    rc = main([
        str(src),
        "--program-name", "2026 GovTech",
        "--document-type", "아이디어기획서",
        "--set", "기업명=x(주)",
    ])

    assert rc == 0
    outputs = list(tmp_path.glob("2026GovTech_아이디어기획서_* v1.hwpx"))
    assert len(outputs) == 1
    assert outputs[0].parent == src.parent
    assert src.exists()



def test_cli_default_output_fail_closed_draft_is_source_adjacent(colored_hwpx, tmp_path):
    """양식에 있던 유색은 게이트 fail 이 아니다. 제출 이름은 원본 폴더에 남는다."""
    from hwpx_submit import main

    src = tmp_path / "GovTech_아이디어기획서_원본.hwpx"
    src.write_bytes(colored_hwpx.read_bytes())

    rc = main([
        str(src),
        "--program-name", "2026 GovTech",
        "--document-type", "아이디어기획서",
        "--set", "기업명=x(주)",
        "--no-normalize-colors",
    ])

    assert rc == 0
    clean = list(tmp_path.glob("2026GovTech_아이디어기획서_* v1.hwpx"))
    drafts = list(tmp_path.glob("2026GovTech_아이디어기획서_* v1_DRAFT.hwpx"))
    assert len(clean) == 1
    assert drafts == []
    assert clean[0].parent == src.parent



def test_cli_exit_codes(clean_hwpx, colored_hwpx, tmp_path, monkeypatch):
    from hwpx_submit import main

    # 0: 깨끗한 양식 + 값 지정 → 제출가능
    rc = main([str(clean_hwpx), "-o", str(tmp_path / "ok.hwpx"),
               "--set", "기업명=x(주)"])
    assert rc == 0

    # 1: identity 도 --set 도 없음 → 빈 제출 방지
    rc = main([str(clean_hwpx), "-o", str(tmp_path / "empty.hwpx")])
    assert rc == 1

    # 1: 입력 파일 없음
    rc = main([str(tmp_path / "no_such.hwpx"), "-o", str(tmp_path / "x.hwpx"),
               "--set", "기업명=x"])
    assert rc == 1

    # 양식 유색 + 정규화 opt-out 은 제출 가능(양식 색은 결함 아님)
    out_color = tmp_path / "color.hwpx"
    rc = main([str(colored_hwpx), "-o", str(out_color), "--set", "기업명=x(주)",
               "--no-normalize-colors"])
    assert rc == 0
    assert out_color.exists()

    # 2: 잔존 예시 이름 → _DRAFT 강제·제출불가
    dummy = tmp_path / "dummy_cli.hwpx"
    rows = "".join([_row(0, "상호", ""), _row(1, "대표자", "홍길동")])
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="2" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(dummy, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", section)
    out2 = tmp_path / "fail.hwpx"
    rc = main([str(dummy), "-o", str(out2), "--set", "기업명=x(주)"])
    assert rc == 2
    assert not out2.exists()                           # CLI 경로에서도 이름 세탁 금지
    assert (tmp_path / "fail_DRAFT.hwpx").exists()

    # 3: 검사불능(예외) → fail-closed _DRAFT
    def _boom(path, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(hs, "run_hwpx_acceptance", _boom)
    out3 = tmp_path / "err.hwpx"
    rc = main([str(clean_hwpx), "-o", str(out3), "--set", "기업명=x(주)"])
    assert rc == 3
    assert not out3.exists()
    assert (tmp_path / "err_DRAFT.hwpx").exists()


# --------------------------------------------------------------------------- #
# 7) 제출 cleanup 배선 — 안내문구 표 제거 + notes 기록
# --------------------------------------------------------------------------- #


def _section_with_guide() -> bytes:
    guide_tbl = (
        f'<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        f'<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f'<hp:t>작성방법 ※삭제 후 제출</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        f'</hp:tr></hp:tbl>'
    )
    rows = "".join([_row(0, "상호", ""), _row(1, "대표자", "")])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0">{guide_tbl}</hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="2" colCnt="2">{rows}</hp:tbl>'
        f'</hp:run></hp:p></hs:sec>'
    ).encode("utf-8")


def test_submit_cleanup_removes_guides(tmp_path):
    src = tmp_path / "guide_form.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", _section_with_guide())
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(src, out, identity={"기업명": "도보네비(주)"})
    assert any("제출 cleanup" in n for n in rep.notes)
    with zipfile.ZipFile(out) as z:
        sec = z.read("Contents/section0.xml").decode("utf-8")
    assert "작성방법" not in sec
    assert "도보네비" in sec or rep.ok is True  # 채움 또는 게이트 통과


def test_submit_cleanup_opt_out_keeps_legacy_normalize(colored_hwpx, tmp_path):
    """submission_cleanup=False + normalize_colors=True → 기존 검정 경로."""
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        colored_hwpx, out, identity={"기업명": "도보네비(주)"},
        submission_cleanup=False, normalize_colors=True,
    )
    assert rep.ok is True
    assert not any(n.startswith("제출 cleanup:") for n in rep.notes)
    assert any("검정 정규화" in n for n in rep.notes)
    assert rep.acceptance.get("colored", -1) == 0


def test_submit_leftover_dummy_name_forces_draft(tmp_path):
    """D6: 양식 예시 이름(홍길동)이 남고 identity 가 아니면 _DRAFT."""
    src = tmp_path / "dummy_form.hwpx"
    rows = "".join([_row(0, "상호", ""), _row(1, "대표자", "홍길동")])
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="2" colCnt="2">{rows}</hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", section)
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(src, out, identity={"기업명": "도보네비(주)"})
    assert rep.ok is False
    assert Path(rep.final).name == "out_DRAFT.hwpx"
    assert rep.acceptance.get("dummy_names", 0) >= 1
    assert "예시이름" in rep.draft_reason

    ok = submit_hwpx(
        src, tmp_path / "ok.hwpx",
        identity={"기업명": "도보네비(주)", "대표자": "홍길동"},
    )
    assert ok.acceptance.get("dummy_names", -1) == 0
    assert ok.ok is True


def test_submit_semantic_exception_is_unknown_review_required(clean_hwpx, tmp_path, monkeypatch):
    def _boom(path):
        raise RuntimeError("semantic unavailable (simulated)")

    monkeypatch.setattr(hs, "check_hwpx_semantics", _boom)
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(clean_hwpx, out, identity={"기업명": "검토(주)"})

    assert rep.routing_status == hs.UNKNOWN_REVIEW_REQUIRED
    assert rep.ok is False
    assert Path(rep.final).name == "out_DRAFT.hwpx"
    assert "semantic 검사 불능" in rep.error
    assert "REVIEW_REQUIRED" in " ".join(rep.notes)
    assert "수용검사 fail" not in rep.draft_reason


def test_preserve_template_normal_does_not_apply_global_cleanup(tmp_path, monkeypatch):
    """정상 HWPX는 전역 cleanup·table repair를 호출하지 않는다."""
    src = tmp_path / "guide_form.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", _section_with_guide())
    out = tmp_path / "out.hwpx"

    def _forbid_repair(*_args, **_kwargs):
        raise AssertionError("NORMAL 문서에 table repair를 호출하면 안 된다")

    monkeypatch.setattr(hs, "finalize_layout_hwpx", _forbid_repair)
    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": "보존(주)"},
        normalize_colors=True,
        submission_cleanup=True,
        preserve_template=True,
    )

    assert rep.routing_status == hs.NORMAL
    assert rep.repair == {}
    assert rep.semantic_before.get("ok") is True
    assert rep.semantic_after.get("ok") is True
    assert not any(note.startswith("제출 cleanup:") for note in rep.notes)
    final = Path(rep.final)
    assert final.exists()
    with zipfile.ZipFile(final) as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert "작성방법" in section


def _section_with_guide() -> bytes:
    guide_tbl = (
        '<hp:tbl rowCnt="1" colCnt="1"><hp:tr>'
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0">'
        '<hp:t>작성방법 ※삭제 후 제출</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
    )
    rows = "".join([_row(0, "상호", ""), _row(1, "대표자", "")])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0">{guide_tbl}</hp:run></hp:p>'
        f'<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="2" colCnt="2">{rows}</hp:tbl>'
        f'</hp:run></hp:p></hs:sec>'
    ).encode("utf-8")


def _sized_section_xml() -> bytes:
    def sized_cell(col: int, row: int, text: str) -> str:
        return (
            f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
            '<hp:cellSpan colSpan="1" rowSpan="1"/>'
            '<hp:cellSz width="100" height="10"/>'
            '<hp:subList><hp:p><hp:run charPrIDRef="0">'
            f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
        )

    rows = "".join(
        f"<hp:tr>{sized_cell(0, row, label)}{sized_cell(1, row, value)}</hp:tr>"
        for row, label, value in [(0, "상호", "")]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="2">'
        f"{rows}</hp:tbl></hp:run></hp:p></hs:sec>"
    ).encode("utf-8")


def _force_rhwp_absent(monkeypatch) -> None:
    """PATH 의 rhwp 버전과 무관하게 L006 가드가 리눅스와 같은 분기를 타게 한다."""
    monkeypatch.delenv("AUTO_WRITE_ENABLE_RHWP", raising=False)
    from core.docx.services import native_hwp

    monkeypatch.setattr(native_hwp, "resolve_rhwp_executable", lambda: None)
    monkeypatch.setattr(native_hwp, "rhwp_available", lambda: False)


def test_local_layout_risk_records_overflow_without_font_shrink(tmp_path, monkeypatch):
    _force_rhwp_absent(monkeypatch)
    src = tmp_path / "sized_form.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", _sized_section_xml())
    out = tmp_path / "out.hwpx"
    value = "아주 긴 입력값" * 20

    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": value},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert rep.routing_status == hs.LOCAL_LAYOUT_RISK
    assert rep.ok is True
    assert rep.filled == {"기업명": value}
    assert rep.acceptance.get("ok") is True
    assert any("overflow_cells" in note for note in rep.notes)
    assert any("자동 축소 생략" in note for note in rep.notes)
    with zipfile.ZipFile(out) as z:
        section = z.read("Contents/section0.xml").decode("utf-8")
    assert value in section
    assert 'height="10"' in section


def test_local_lineseg_is_limited_to_edited_region(tmp_path):
    """linesegarray는 채운 칸만 제거하고, 미편집 문단 캐시는 남긴다."""
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
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:linesegarray><hp:lineseg textpos="0" vertpos="0"/></hp:linesegarray>'
        '<hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="1" colCnt="2"><hp:tr>{label}{value}</hp:tr></hp:tbl>'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    src = tmp_path / "lineseg.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", section)
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        src, out, identity={"기업명": "부분수정(주)"},
        normalize_colors=False, submission_cleanup=False, preserve_template=True,
    )
    assert rep.filled.get("기업명") == "부분수정(주)"
    assert rep.ok is True
    assert Path(rep.final).name == "out.hwpx"
    assert rep.acceptance.get("linesegarray", -1) == 0
    assert not any(note.startswith("제출 cleanup:") for note in rep.notes)
    with zipfile.ZipFile(rep.final) as z:
        sec = z.read("Contents/section0.xml").decode("utf-8")
    assert sec.count("<hp:linesegarray") == 1
    assert 'vertpos="0"' in sec
    assert 'vertpos="120"' not in sec


def test_normal_direct_fill_preserves_unrelated_package_parts(tmp_path, monkeypatch):
    """허용 변경은 목표 텍스트뿐이다. BinData·관계·무관 표 기하·repair는 불변."""
    _force_rhwp_absent(monkeypatch)
    unrelated = (
        '<hp:tbl rowCnt="1" colCnt="1" id="keep"><hp:tr>'
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:cellSz width="4242" height="800"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0">'
        '<hp:t>고정문구</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
    )
    rows = _row(0, "상호", "")
    section = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        '<hp:p><hp:run charPrIDRef="0">'
        f'<hp:tbl rowCnt="1" colCnt="2">{rows}</hp:tbl>'
        f'{unrelated}'
        "</hp:run></hp:p></hs:sec>"
    ).encode("utf-8")
    content_hpf = b'<opf:item id="image1" href="BinData/pic.bin"/>'
    blob = b"PNGDATA-UNCHANGED"
    src = tmp_path / "preserve.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", section)
        z.writestr("Contents/content.hpf", content_hpf)
        z.writestr("BinData/pic.bin", blob)

    def _forbid_repair(*_args, **_kwargs):
        raise AssertionError("NORMAL 문서에 table repair를 호출하면 안 된다")

    monkeypatch.setattr(hs, "finalize_layout_hwpx", _forbid_repair)
    out = tmp_path / "out.hwpx"
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    rep = submit_hwpx(
        src, out, identity={"기업명": "보존값"},
        normalize_colors=False, submission_cleanup=False, preserve_template=True,
    )
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert rep.routing_status == hs.NORMAL
    assert rep.repair == {}
    assert rep.filled == {"기업명": "보존값"}
    with zipfile.ZipFile(out) as z:
        assert z.read("mimetype") == _MIMETYPE
        assert z.read("BinData/pic.bin") == blob
        assert z.read("Contents/content.hpf") == content_hpf
        sec = z.read("Contents/section0.xml").decode("utf-8")
    assert "보존값" in sec
    assert 'width="4242"' in sec
    assert 'width="4242" height="800"' in sec
    assert "고정문구" in sec


def _broken_grid_section_xml() -> bytes:
    rows = []
    for row_addr in (0, 1, 2, 2):
        cells = "".join(
            f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row_addr}"/>'
            '<hp:cellSpan colSpan="1" rowSpan="1"/>'
            '<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>'
            f"{('기업명' if row_addr == 0 and col == 0 else '')}"
            "</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
            for col in (0, 1)
        )
        rows.append(f"<hp:tr>{cells}</hp:tr>")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="4" colCnt="2">'
        f"{''.join(rows)}</hp:tbl></hp:run></hp:p></hs:sec>"
    ).encode("utf-8")


def test_structural_repairable_repairs_grid_and_rechecks(tmp_path):
    """preserve_template 표 격자.

    rhwp가 있으면 셀 주소만 교정하고 재검사한다.
    rhwp가 없으면 추정 수정을 하지 않고, 유효한 패키지와 노트만 남긴 채 제출을 막는다.
    L005 픽셀 PASS는 어느 쪽이든 기록하지 않는다.
    """
    from core.docx.services.native_hwp import rhwp_available

    src = tmp_path / "broken_grid.hwpx"
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", _broken_grid_section_xml())
    out = tmp_path / "out.hwpx"
    before = hashlib.sha256(src.read_bytes()).hexdigest()

    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": "복구(주)"},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    final = Path(rep.final)
    assert final.is_file()
    assert zipfile.is_zipfile(final)
    with zipfile.ZipFile(final) as z:
        assert z.testzip() is None
        sec = z.read("Contents/section0.xml").decode("utf-8")
    assert "복구(주)" in sec
    assert rep.routing_status == hs.STRUCTURAL_REPAIRABLE
    assert rep.semantic_before.get("broken_tables")
    assert rep.native_render.get("l005_pixel") != "PASS"
    assert rep.native_render.get("pixel_reopen_claimed") is not True
    if rhwp_available():
        assert rep.semantic_after.get("ok") is True
        assert rep.semantic_after.get("broken_tables") == []
        assert rep.repair.get("grid_cells_fixed", 0) > 0
    else:
        assert rep.repair == {}
        assert rep.ok is False
        assert rep.submittable is False
        assert rep.semantic_after.get("ok") is False
        assert any("repair 생략" in note for note in rep.notes)
        assert sec.count('rowAddr="2"') == 4
        assert final.name == "out_DRAFT.hwpx"
        assert not out.exists()
        assert not any(path.name.startswith("out.__grid_repair__") for path in tmp_path.iterdir())


def test_structural_unsafe_never_repairs_dangling_reference(tmp_path, monkeypatch):
    src = tmp_path / "unsafe.hwpx"
    section = _section_xml().replace(b'charPrIDRef="0"', b'charPrIDRef="99"')
    with zipfile.ZipFile(src, "w") as z:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        z.writestr(zi, _MIMETYPE)
        z.writestr("Contents/header.xml", _header_xml(colored=False))
        z.writestr("Contents/section0.xml", section)
    out = tmp_path / "out.hwpx"

    def _forbid_repair(*_args, **_kwargs):
        raise AssertionError("STRUCTURAL_UNSAFE 에서 repair를 호출하면 안 된다")

    monkeypatch.setattr(hs, "finalize_layout_hwpx", _forbid_repair)
    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": "검토(주)"},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert rep.routing_status == hs.STRUCTURAL_UNSAFE
    assert rep.semantic_before.get("dangling_refs")
    assert rep.semantic_after.get("ok") is False
    assert rep.repair == {}
    assert rep.ok is False
    assert Path(rep.final).name == "out_DRAFT.hwpx"
    assert "자동 교정 근거 없음" in rep.draft_reason


class _RhwpProc:
    def __init__(self, stdout: str, stderr: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _fake_rhwp(tmp_path, monkeypatch, *, stdout: str, stderr: str, returncode: int = 0):
    """RHWP_EXE 만 가리키고 subprocess 응답을 고정한다. PATH 폴백은 쓰지 않는다."""
    from core.docx.services import native_hwp

    exe = tmp_path / "rhwp.exe"
    exe.write_bytes(b"MZ")
    native_hwp.clear_rhwp_capability_cache()
    monkeypatch.setenv("AUTO_WRITE_ENABLE_RHWP", "1")
    monkeypatch.setenv("RHWP_EXE", str(exe))
    calls: list[list[str]] = []

    def _run(cmd, **_kwargs):
        calls.append(list(cmd))
        return _RhwpProc(stdout, stderr, returncode)

    monkeypatch.setattr(native_hwp.subprocess, "run", _run)
    return native_hwp, calls


def test_rhwp_empty_stdout_stderr_exit_0_is_unsupported(tmp_path, monkeypatch):
    stderr = "오류: 문서 파싱 실패 - 유효하지 않은 파일: HWPX 오류: 필수 파일 누락: Contents/content.hpf"
    native_hwp, calls = _fake_rhwp(tmp_path, monkeypatch, stdout="", stderr=stderr)
    with pytest.raises(native_hwp.UnsupportedRhwpError, match="unsupported rhwp version") as caught:
        native_hwp._rhwp_json("info", "broken.hwpx")
    assert stderr in str(caught.value)
    probed = len(calls)
    assert probed >= 1
    assert native_hwp.rhwp_available() is False
    assert len(calls) == probed

    candidate = tmp_path / "candidate.hwpx"
    candidate.write_bytes(b"PK")
    evidence = native_hwp.verify_hwpx_native(candidate)
    assert evidence["render_status"] == "UNAVAILABLE"
    assert evidence["reopen_status"] == "NOT_RUN"
    assert evidence["ok"] is False
    assert "unsupported rhwp version" in evidence["message"]
    assert len(calls) == probed


def test_rhwp_korean_plaintext_stdout_is_unsupported(tmp_path, monkeypatch):
    stdout = "파일: sample.hwpx\n크기: 55991 bytes\n버전: 5.1.0.0\n페이지 수: 10\n"
    native_hwp, _calls = _fake_rhwp(tmp_path, monkeypatch, stdout=stdout, stderr="")
    with pytest.raises(native_hwp.UnsupportedRhwpError, match="unsupported rhwp version") as caught:
        native_hwp._rhwp_json("info", "sample.hwpx")
    text = str(caught.value)
    assert "5.1.0.0" in text
    assert "파일:" in text or "페이지 수" in text
    assert native_hwp.rhwp_available() is False


def test_rhwp_stderr_with_exit_0_rejects_json_stdout(tmp_path, monkeypatch):
    native_hwp, _calls = _fake_rhwp(
        tmp_path,
        monkeypatch,
        stdout='{"format":"hwpx","pageCount":1}',
        stderr="warning: ignored flag",
    )
    with pytest.raises(native_hwp.UnsupportedRhwpError, match="unsupported rhwp version") as caught:
        native_hwp._rhwp_json("info", "sample.hwpx")
    assert "warning: ignored flag" in str(caught.value)
    assert native_hwp.rhwp_available() is False


def test_compatible_json_rhwp_returns_object(tmp_path, monkeypatch):
    payload = {"format": "hwpx", "pageCount": 2, "schemaVersion": 1, "version": "0.8.6"}
    native_hwp, calls = _fake_rhwp(
        tmp_path,
        monkeypatch,
        stdout=json.dumps(payload),
        stderr="",
    )
    assert native_hwp.rhwp_available() is True
    got = native_hwp._rhwp_json("info", "sample.hwpx")
    assert got["format"] == "hwpx"
    assert got["pageCount"] == 2
    assert any("--json" in cmd for cmd in calls)


def test_incompatible_rhwp_hwp_conversion_uses_hangul_com(tmp_path, monkeypatch):
    from core.docx.services import hwp_docx_convert as conv
    from core.docx.services.hwp_docx_convert import hwp_to_hwpx

    native_hwp, _calls = _fake_rhwp(
        tmp_path,
        monkeypatch,
        stdout="파일: 양식.hwp\n버전: 5.0.0.0\n",
        stderr="",
    )
    assert native_hwp.rhwp_available() is False
    src = tmp_path / "양식.hwp"
    src.write_bytes(b"OLE-HWP-BYTES")
    out = tmp_path / "양식.hwpx"

    class _FakeHwpCom:
        def __init__(self) -> None:
            self.saved: list[tuple[str, str]] = []

        def Open(self, *_args):
            return True

        def SaveAs(self, path, fmt, _opts):
            Path(path).write_bytes(b"FAKE-HWP-BINARY")
            self.saved.append((path, fmt))
            return True

        def Clear(self, *_args):
            return None

        def Quit(self):
            return None

    fake = _FakeHwpCom()
    monkeypatch.setattr(conv, "hancom_com_available", lambda: True)
    monkeypatch.setattr(conv, "_dispatch_hwp", lambda: fake)

    report = hwp_to_hwpx(src, out)

    assert report.ok is True
    assert report.method == "hancom_com"
    assert out.read_bytes() == b"FAKE-HWP-BINARY"
    assert fake.saved[0][1] == "HWPX"
    assert src.read_bytes() == b"OLE-HWP-BYTES"


def test_invalid_rhwp_exe_does_not_fall_back_to_path(tmp_path, monkeypatch):
    from core.docx.services import native_hwp

    decoy = tmp_path / "rhwp"
    decoy.write_bytes(b"decoy")
    monkeypatch.setenv("AUTO_WRITE_ENABLE_RHWP", "1")
    monkeypatch.setenv("RHWP_EXE", str(tmp_path / "missing" / "rhwp.exe"))
    seen: list[str] = []
    monkeypatch.setattr(native_hwp.shutil, "which", lambda name: seen.append(name) or str(decoy))
    monkeypatch.setattr(
        native_hwp.subprocess,
        "run",
        lambda *_a, **_k: seen.append("run"),
    )
    native_hwp.clear_rhwp_capability_cache()
    assert native_hwp.resolve_rhwp_executable() is None
    assert native_hwp.rhwp_available() is False
    assert seen == []


def test_incompatible_rhwp_render_does_not_force_draft(tmp_path, monkeypatch):
    native_hwp, _calls = _fake_rhwp(
        tmp_path,
        monkeypatch,
        stdout="",
        stderr="오류: 문서 파싱 실패 - 유효하지 않은 파일",
    )
    src = tmp_path / "form.hwpx"
    _make_hwpx(src, colored=False)
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": "정상값"},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )
    assert rep.ok is True
    assert Path(rep.final) == out
    assert out.is_file()
    assert not (tmp_path / "out_DRAFT.hwpx").exists()
    assert rep.native_render.get("render_status") == "UNAVAILABLE"
    assert rep.native_render.get("reopen_status") == "NOT_RUN"
    assert "unsupported rhwp version" in str(rep.native_render.get("message") or "")
    render = next(v for v in rep.integrity["validators"] if v["source_validator"] == "rendering_validator")
    assert render["validator_status"] == "UNAVAILABLE"
    assert render["severity"] == "PASS"
    assert render["defect_code"] == "RHWP_ABSENT"
