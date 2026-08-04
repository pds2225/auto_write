"""test_pure_hwpx_self_diagnose_exit.py — HWPX 자가진단 종료코드 계약 안전망.

무인 파이프라인은 이 CLI 의 **종료코드만 보고** 다음 행동을 정한다.

    0 = 제출 가능 / 1 = 입력 오류 / 2 = 제출 불가 / 3 = 검사 불능(환경 문제)

'2(문서를 고쳐라)'와 '3(환경을 고쳐라)'이 뒤섞이면 자동 체인이 엉뚱한 조치를 한다.
그래서 종료코드는 어떤 부수효과(JSON 저장 실패 등)로도 흔들리면 안 된다.

실제 HWPX 를 열지 않고 진단 함수를 가짜로 갈아끼워 **분기와 종료코드만** 검증한다
(ZIP·한글 COM 미사용). 야간 안전망(2026-08-04).
"""

from __future__ import annotations

import json

import pytest

import hwpx_self_diagnose as mod
from hwpx_self_diagnose import GateItem, HwpxDiagnoseReport, diagnose_hwpx


def _report(*, ok: bool, gates=(), notes=()) -> HwpxDiagnoseReport:
    return HwpxDiagnoseReport(
        path="x.hwpx", ok=ok, gates=list(gates),
        coverage={"overall_rate": 0.5, "sections": []}, notes=list(notes),
    )


@pytest.fixture
def hwpx(tmp_path):
    """존재하기만 하면 되는 더미 .hwpx (내용은 읽지 않는다)."""
    p = tmp_path / "제출본.hwpx"
    p.write_bytes(b"")
    return p


def _stub(monkeypatch, report=None, *, raises: Exception | None = None):
    seen: dict = {}

    def _fake(path, *, require_specialty_checked=False):
        seen["path"] = str(path)
        seen["require_specialty_checked"] = require_specialty_checked
        if raises is not None:
            raise raises
        return report

    monkeypatch.setattr(mod, "diagnose_hwpx", _fake)
    return seen


# --- 자료구조 ----------------------------------------------------------------

def test_gate_item_as_dict():
    assert GateItem("L037", "pass", "서식 위주").as_dict() == {
        "rule": "L037", "status": "pass", "detail": "서식 위주"
    }


def test_report_as_dict_serializes_gates():
    rep = _report(ok=True, gates=[GateItem("인적", "pass")])
    data = rep.as_dict()
    assert data["ok"] is True
    assert data["gates"] == [{"rule": "인적", "status": "pass", "detail": ""}]


def test_report_defaults_to_not_ok():
    assert HwpxDiagnoseReport(path="x.hwpx").ok is False


# --- diagnose_hwpx: 입력 게이트(ZIP 열기 전 조기 반환) ------------------------

def test_diagnose_missing_file_reports_input_gate(tmp_path):
    rep = diagnose_hwpx(tmp_path / "없음.hwpx")
    assert rep.ok is False
    assert [(g.rule, g.status) for g in rep.gates] == [("input", "fail")]
    assert rep.gates[0].detail == "파일 없음"


def test_diagnose_wrong_extension_reports_input_gate(tmp_path):
    docx = tmp_path / "제출본.docx"
    docx.write_bytes(b"")
    rep = diagnose_hwpx(docx)
    assert rep.ok is False
    assert rep.gates[0].rule == "input"
    assert "HWPX 아님" in rep.gates[0].detail


# --- main(): 종료코드 계약 ----------------------------------------------------

def test_exit_0_when_submittable(monkeypatch, hwpx, capsys):
    _stub(monkeypatch, _report(ok=True))
    assert mod.main([str(hwpx)]) == 0


def test_exit_2_when_not_submittable(monkeypatch, hwpx, capsys):
    _stub(monkeypatch, _report(ok=False, gates=[GateItem("L037", "fail", "공고 잔존")]))
    assert mod.main([str(hwpx)]) == 2


def test_exit_1_when_file_is_missing(tmp_path, capsys):
    assert mod.main([str(tmp_path / "없음.hwpx")]) == 1


def test_exit_1_when_input_gate_failed(monkeypatch, hwpx, capsys):
    # 확장자 오류 등 '입력' 문제는 문서 결함(2)이 아니라 입력오류(1)로 보고한다.
    _stub(monkeypatch, _report(ok=False, gates=[GateItem("input", "fail", "HWPX 아님: .docx")]))
    assert mod.main([str(hwpx)]) == 1


def test_exit_3_when_inspection_is_impossible(monkeypatch, hwpx, capsys):
    _stub(monkeypatch, _report(ok=False, gates=[GateItem("zip", "fail")], notes=["검사불능"]))
    assert mod.main([str(hwpx)]) == 3


def test_exit_3_when_diagnose_raises(monkeypatch, hwpx, capsys):
    _stub(monkeypatch, raises=RuntimeError("의존성 없음"))
    assert mod.main([str(hwpx)]) == 3


def test_require_specialty_flag_is_forwarded(monkeypatch, hwpx, capsys):
    seen = _stub(monkeypatch, _report(ok=True))
    mod.main([str(hwpx), "--require-specialty"])
    assert seen["require_specialty_checked"] is True

    seen2 = _stub(monkeypatch, _report(ok=True))
    mod.main([str(hwpx)])
    assert seen2["require_specialty_checked"] is False


# --- --json 부수효과가 종료코드를 오염시키지 않는다 ---------------------------

def test_json_is_written_when_path_is_valid(monkeypatch, hwpx, tmp_path, capsys):
    _stub(monkeypatch, _report(ok=True, gates=[GateItem("L024", "pass")]))
    out = tmp_path / "진단.json"
    assert mod.main([str(hwpx), "--json", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is True and data["gates"][0]["rule"] == "L024"


def test_unwritable_json_path_does_not_change_exit_code(monkeypatch, hwpx, tmp_path, capsys):
    # 부모 폴더가 없는 경로 → 저장은 실패하지만 진단 결과(0)는 그대로여야 한다.
    _stub(monkeypatch, _report(ok=True))
    bad = tmp_path / "없는폴더" / "진단.json"
    assert mod.main([str(hwpx), "--json", str(bad)]) == 0
    assert not bad.exists()
    assert "JSON 저장 실패" in capsys.readouterr().err


def test_unwritable_json_keeps_not_submittable_code(monkeypatch, hwpx, tmp_path, capsys):
    _stub(monkeypatch, _report(ok=False, gates=[GateItem("인적", "fail")]))
    bad = tmp_path / "없는폴더" / "진단.json"
    assert mod.main([str(hwpx), "--json", str(bad)]) == 2


def test_diagnosis_is_still_printed_when_json_fails(monkeypatch, hwpx, tmp_path, capsys):
    _stub(monkeypatch, _report(ok=False, gates=[GateItem("L037", "fail", "공고 잔존")]))
    mod.main([str(hwpx), "--json", str(tmp_path / "없는폴더" / "x.json")])
    out = capsys.readouterr().out
    assert "HWPX 진단" in out and "L037" in out
