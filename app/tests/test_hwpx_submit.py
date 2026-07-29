"""test_hwpx_submit.py — HWPX 제출 파이프라인(채움→수용검사 게이트→_DRAFT 강제) 검증.

B②(게이트 배선)+B③(제출 파이프라인): fill_hwpx 로 채운 산출물을 run_hwpx_acceptance
게이트로 판정하고, fail/검사불능이면 force_draft_name(단일 출처)으로 _DRAFT 를 강제해
제출 이름으로 절대 통과시키지 않는다(fail-closed, R9). 원본 미수정도 확인한다.
"""

from __future__ import annotations

import hashlib
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
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties>'
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
# 2) 게이트 fail(유색 charPr) → _DRAFT 강제·원래 이름 잔존 금지
# --------------------------------------------------------------------------- #


def test_submit_gate_fail_forces_draft(colored_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    # 검정 정규화 opt-out → 유색 예시체가 잔존 → 게이트 fail → _DRAFT 검증(보존)
    rep = submit_hwpx(colored_hwpx, out, identity={"기업명": "도보네비(주)"},
                      normalize_colors=False)
    assert rep.ok is False
    final = Path(rep.final)
    assert final.name == "out_DRAFT.hwpx"              # _DRAFT 강제 명명
    assert final.exists()
    assert not out.exists()                            # 제출 이름 파일 잔존 금지
    assert rep.draft_marked is True
    assert rep.acceptance.get("colored", 0) >= 1
    assert "유색" in rep.draft_reason                  # 결함 요약이 사유에 명시
    # 채움 자체는 정상 수행(값은 들어감 — 판정만 제출불가)
    assert rep.filled == {"기업명": "도보네비(주)"}


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
    def _boom(path):
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
# 4) acceptance_gate=False → 게이트 스킵·이름 유지
# --------------------------------------------------------------------------- #


def test_submit_no_gate_flag(colored_hwpx, tmp_path):
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        colored_hwpx, out, identity={"기업명": "x(주)"}, acceptance_gate=False
    )
    assert rep.ok is True                              # 채움 성공 기준
    assert rep.final == str(out)
    assert out.exists()
    assert rep.draft_marked is False
    assert rep.acceptance == {}                        # 게이트 미실행
    assert any("생략" in n for n in rep.notes)          # 스킵 사실을 정직하게 노트


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

    # 2: 게이트 fail(유색) → _DRAFT 강제·제출불가 (검정 정규화 opt-out 으로 유색 잔존)
    out2 = tmp_path / "fail.hwpx"
    rc = main([str(colored_hwpx), "-o", str(out2), "--set", "기업명=x(주)",
               "--no-normalize-colors"])
    assert rc == 2
    assert not out2.exists()                           # CLI 경로에서도 이름 세탁 금지
    assert (tmp_path / "fail_DRAFT.hwpx").exists()

    # 3: 검사불능(예외) → fail-closed _DRAFT
    def _boom(path):
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
