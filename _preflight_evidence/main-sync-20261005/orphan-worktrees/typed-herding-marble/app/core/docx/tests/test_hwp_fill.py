"""test_hwp_fill.py — HWP 양식 표 채우기 + 본문 보강 end-to-end (Stream 3).

검증 포인트:
  - 표 포함 합성 HWPX 픽스처가 실제 python-docx 표로 변환되고(최고위험 디테일),
    identity 라벨 매칭으로 표 빈칸이 채워진다(≥1).
  - empty-plan(identity·fill_plan 없음) → no-op(0칸, 에러 없음, 변환은 진행).
  - 원본 미수정 / out==in ValueError.
  - COM 부재(hancom_com_available=False) → ok=False, DOCX-only, 안내, 예외 없음.
  - 본문 보강이 제출불가(_DRAFT) 신호를 주면 출력 HWP 도 _DRAFT 명명.

DOCX→HWP 는 한글 COM 대화형 전용이라 _dispatch_hwp monkeypatch 로 성공을
시뮬레이션한다(빈 .hwp 파일 생성). 본문 보강(run_bizplan_autopilot)은
use_ai=False·brief="" 로 생략하거나(채움 단위 테스트), 명시적으로 monkeypatch
한다(DRAFT 전파 테스트).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from docx import Document

import auto_write.services.hwp_docx_convert as conv_mod
import auto_write.services.hwp_fill as fill_mod
from auto_write.services.hwp_fill import fill_hwp


# --- 픽스처: 라벨행 + 빈칸을 가진 표를 품은 HWPX ---------------------------------

_SECTION_WITH_TABLE = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p id="1"><hp:run><hp:t>일반현황</hp:t></hp:run></hp:p>
  <hp:p id="2"><hp:run>
    <hp:tbl rowCnt="2" colCnt="2">
      <hp:tr>
        <hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList></hp:tc>
        <hp:tc><hp:cellAddr colAddr="1" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList></hp:tc>
      </hp:tr>
      <hp:tr>
        <hp:tc><hp:cellAddr colAddr="0" rowAddr="1"/><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t>대표자</hp:t></hp:run></hp:p></hp:subList></hp:tc>
        <hp:tc><hp:cellAddr colAddr="1" rowAddr="1"/><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p><hp:run><hp:t></hp:t></hp:run></hp:p></hp:subList></hp:tc>
      </hp:tr>
    </hp:tbl>
  </hp:run></hp:p>
</hs:sec>"""


def _make_hwpx_with_table(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/hwpx")
        z.writestr("Contents/section0.xml", _SECTION_WITH_TABLE)
        z.writestr("Preview/PrvText.txt", "일반현황\n기업명\n대표자")


def _docx_table_rows(path: Path) -> list[list[str]]:
    doc = Document(str(path))
    out: list[list[str]] = []
    for t in doc.tables:
        for row in t.rows:
            out.append([c.text for c in row.cells])
    return out


class _FakeHwpCom:
    """한글 COM 흉내 — SaveAs 가 실제로 파일을 만들어야 존재 검사를 통과한다."""

    def RegisterModule(self, *a):
        return True

    def SetMessageBoxMode(self, *a):
        return 0

    def Open(self, path, fmt, opts):
        return True

    def SaveAs(self, path, fmt, opts):
        Path(path).write_bytes(b"FAKE-HWP-BINARY")
        return True

    def Clear(self, *a):
        pass

    def Quit(self):
        pass


def _patch_com(monkeypatch) -> None:
    """DOCX→HWP 가 COM 으로 성공하도록(빈 .hwp 생성) 시뮬레이션한다.

    HWP→DOCX 는 COM 을 끄고 구조 변환 경로를 쓰도록 hwp_to_docx 를 래핑한다
    (FakeCom 으로는 HWPX 구조를 복원할 수 없으므로)."""
    monkeypatch.setattr(conv_mod, "hancom_com_available", lambda: True)
    monkeypatch.setattr(conv_mod, "_dispatch_hwp", lambda: _FakeHwpCom())

    real_hwp_to_docx = conv_mod.hwp_to_docx

    def _structural(in_path, out_path=None, *, use_com=True):
        return real_hwp_to_docx(in_path, out_path, use_com=False)

    monkeypatch.setattr(fill_mod, "hwp_to_docx", _structural)


# --- 검증 ---------------------------------------------------------------------

def test_fixture_converts_to_real_table(tmp_path: Path) -> None:
    """최고위험 디테일: 합성 HWPX 가 실제 표(row0=[기업명, 빈칸])로 변환된다."""
    from auto_write.document_ingest import _convert_hwpx_to_docx

    src = tmp_path / "form.hwpx"
    out = tmp_path / "form.docx"
    _make_hwpx_with_table(src)
    _convert_hwpx_to_docx(src, out)
    rows = _docx_table_rows(out)
    assert rows == [["기업명", ""], ["대표자", ""]]


def test_out_equals_in_blocked(tmp_path: Path) -> None:
    src = tmp_path / "form.hwpx"
    _make_hwpx_with_table(src)
    with pytest.raises(ValueError):
        fill_hwp(str(src), str(src))


def test_identity_fills_table(tmp_path: Path, monkeypatch) -> None:
    """identity 주면 표 채움 ≥1, 원본 미수정, 출력 HWP 생성."""
    _patch_com(monkeypatch)
    src = tmp_path / "form.hwpx"
    out = tmp_path / "filled.hwp"
    _make_hwpx_with_table(src)
    before = src.read_bytes()

    r = fill_hwp(
        str(src), str(out),
        identity={"기업명": "테스트(주)", "대표자": "홍길동"},
        use_ai=False,            # 본문 보강 생략(채움만 검증)
    )

    assert r.ok is True
    assert r.filled["identity"] >= 1
    assert Path(r.output).exists()
    assert r.draft_marked is False
    assert src.read_bytes() == before          # 원본 미수정


def test_empty_plan_is_noop(tmp_path: Path, monkeypatch) -> None:
    """identity·fill_plan 둘 다 없으면 0칸 채움 — 에러 없이 변환은 진행."""
    _patch_com(monkeypatch)
    src = tmp_path / "form.hwpx"
    out = tmp_path / "filled.hwp"
    _make_hwpx_with_table(src)

    r = fill_hwp(str(src), str(out), use_ai=False)

    assert r.ok is True
    assert r.filled["identity"] == 0
    assert r.filled["rows"] == 0
    assert Path(r.output).exists()


def test_com_unavailable_docx_only(tmp_path: Path, monkeypatch) -> None:
    """COM 부재 → ok=False, DOCX-only 보존, 안내 notes, 예외 전파 없음."""
    monkeypatch.setattr(conv_mod, "hancom_com_available", lambda: False)
    src = tmp_path / "form.hwpx"
    out = tmp_path / "filled.hwp"
    _make_hwpx_with_table(src)

    r = fill_hwp(
        str(src), str(out),
        identity={"기업명": "테스트(주)"},
        use_ai=False,
    )

    assert r.ok is False
    assert r.output.endswith(".docx")
    assert Path(r.output).exists()
    assert any("COM" in n for n in r.notes)
    assert not out.exists()                    # HWP 는 못 만든다


def test_draft_signal_marks_output(tmp_path: Path, monkeypatch) -> None:
    """본문 보강이 제출불가(_DRAFT)면 출력 HWP 도 _DRAFT 명명."""
    _patch_com(monkeypatch)

    class _FakeBpReport:
        def __init__(self, output_docx: str) -> None:
            self.output_docx = output_docx
            self.draft_marked = True
            self.acceptance_submittable = False
            self.acceptance_verdict = "제출불가"

    def _fake_bp(in_docx, out_docx, **kwargs):
        # 엔진이 _DRAFT 경로로 산출했다고 가정 — 입력 docx 를 그대로 복사.
        draft = Path(out_docx).with_name(Path(out_docx).stem + "_DRAFT.docx")
        import shutil
        shutil.copyfile(in_docx, str(draft))
        return _FakeBpReport(str(draft))

    monkeypatch.setattr(
        "auto_write.services.bizplan_autopilot.run_bizplan_autopilot", _fake_bp)

    src = tmp_path / "form.hwpx"
    out = tmp_path / "filled.hwp"
    _make_hwpx_with_table(src)

    r = fill_hwp(
        str(src), str(out),
        identity={"기업명": "테스트(주)"},
        brief="AI 인재 실증형 사업",       # 본문 보강 트리거
        use_ai=False,
    )

    assert r.draft_marked is True
    assert r.acceptance_verdict == "제출불가"
    assert Path(r.output).stem.endswith("_DRAFT")
    assert Path(r.output).exists()
