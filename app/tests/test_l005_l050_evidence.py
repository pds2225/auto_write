"""L005 한글 GUI 증거와 L050 rhwp export-pdf.

Linux 목 성공은 PASS/mechanized 가 아니다. 커버리지 분류는 바꾸지 않는다.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from auto_write.services import hwpx_submit as hs
from auto_write.services.submission_gates import (
    L005_CHECKLIST,
    hangul_gui_available,
    hangul_pdf_tool,
    l005_pixel_review_status,
    l050_mechanization_status,
    record_l005_pixel_review,
    try_generate_sibling_pdf,
    write_l005_review_template,
)
from core.docx.services import native_hwp
from core.docx.services import submission_gates as gates
from test_hwpx_r9_common_gate import _make_hwpx

_REPO = Path(__file__).resolve().parents[2]
_COVERAGE = _REPO / "app" / "tests" / "lessons_coverage.json"


def _lesson(code: str) -> dict:
    data = json.loads(_COVERAGE.read_text(encoding="utf-8"))
    prefix = code + " |"
    for row in data["lessons"]:
        if str(row["id"]).startswith(prefix):
            return row
    raise AssertionError(code)


def _hide_rhwp(monkeypatch) -> None:
    monkeypatch.delenv("RHWP_EXE", raising=False)
    monkeypatch.setattr(native_hwp.shutil, "which", lambda _name: None)


def _fake_run(dest_bytes: bytes):
    def run(cmd, **_kwargs):
        out = Path(cmd[cmd.index("-o") + 1])
        if dest_bytes:
            out.write_bytes(dest_bytes)

        class Proc:
            returncode = 0 if dest_bytes else 1
            stdout = ""
            stderr = "" if dest_bytes else "export failed"

        return Proc()

    return run


def test_rhwp_exe_beats_path_and_export_args(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "rhwp.exe"
    exe.write_bytes(b"MZ")
    decoy = tmp_path / "rhwp"
    decoy.write_bytes(b"decoy")
    monkeypatch.setenv("RHWP_EXE", f'"{exe}"')
    monkeypatch.setattr(native_hwp.shutil, "which", lambda _name: str(decoy))
    assert hangul_pdf_tool() == str(exe)

    src = tmp_path / "신청서.hwpx"
    src.write_bytes(b"PK")
    calls: list[list[str]] = []

    def run(cmd, **_kwargs):
        calls.append(list(cmd))
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"%PDF-1.4")

        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return Proc()

    monkeypatch.setattr(gates.subprocess, "run", run)
    gen = try_generate_sibling_pdf(src)
    assert gen.generated is True
    assert gen.blocked is False
    assert calls[0][0] == str(exe)
    assert calls[0][1:4] == ["export-pdf", str(src.resolve()), "-o"]
    assert calls[0][4] == str((tmp_path / "신청서.pdf").resolve())
    assert "soffice" not in " ".join(calls[0]).lower()
    # Evidence JSON is written only on win32. Either host must keep mechanized false,
    # and a call with no artifact path stays BLOCKED.
    if sys.platform == "win32":
        evidence = Path(gen.evidence)
        assert evidence.name == "신청서.l050.json"
        assert evidence.is_file()
        proved = l050_mechanization_status(evidence)
        assert proved["status"] == "GENERATED"
        assert proved["mechanized"] is False
    else:
        assert gen.evidence == ""
        assert not (tmp_path / "신청서.l050.json").exists()
    claim = l050_mechanization_status()
    assert claim["status"] == "BLOCKED"
    assert claim["mechanized"] is False
    assert _lesson("L050")["category"] == "gap"


def test_path_rhwp_used_when_env_unset(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "rhwp"
    exe.write_bytes(b"#!/bin/sh\n")
    monkeypatch.delenv("RHWP_EXE", raising=False)
    monkeypatch.setattr(native_hwp.shutil, "which", lambda name: str(exe) if name == "rhwp" else None)
    assert hangul_pdf_tool() == str(exe)


def test_broken_rhwp_exe_does_not_fall_through_to_path(tmp_path: Path, monkeypatch) -> None:
    decoy = tmp_path / "rhwp"
    decoy.write_bytes(b"decoy")
    monkeypatch.setenv("RHWP_EXE", str(tmp_path / "missing" / "rhwp.exe"))
    monkeypatch.setattr(native_hwp.shutil, "which", lambda _name: str(decoy))
    assert hangul_pdf_tool() is None
    src = tmp_path / "신청서.hwpx"
    src.write_bytes(b"PK")
    called: list = []
    monkeypatch.setattr(gates.subprocess, "run", lambda *args, **kwargs: called.append(args))
    gen = try_generate_sibling_pdf(src)
    assert called == []
    assert gen.generated is False
    assert gen.blocked is True
    assert "BLOCKED" in gen.reason
    assert not (tmp_path / "신청서.pdf").exists()


def test_soffice_is_not_a_hangul_pdf_tool(tmp_path: Path, monkeypatch) -> None:
    soffice = tmp_path / "soffice"
    soffice.write_bytes(b"lo")
    monkeypatch.delenv("RHWP_EXE", raising=False)
    monkeypatch.setattr(native_hwp.shutil, "which", lambda _name: str(soffice))
    assert hangul_pdf_tool() is None
    source = inspect.getsource(try_generate_sibling_pdf)
    assert "win32com" not in source
    assert "Dispatch" not in source
    assert '"soffice"' not in source
    assert "'soffice'" not in source


def test_export_failure_stays_blocked(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "rhwp.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("RHWP_EXE", str(exe))
    monkeypatch.setattr(gates.subprocess, "run", _fake_run(b""))
    src = tmp_path / "신청서.hwp"
    src.write_bytes(b"HWP")
    gen = try_generate_sibling_pdf(src)
    assert gen.generated is False
    assert gen.blocked is True
    assert "BLOCKED" in gen.reason
    assert not (tmp_path / "신청서.pdf").exists()
    assert l050_mechanization_status()["mechanized"] is False


def test_linux_ignores_windows_l050_evidence(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "신청서.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    evidence = tmp_path / "신청서.l050.json"
    evidence.write_text(
        json.dumps(
            {
                "lesson": "L050",
                "generated": True,
                "platform": "win32",
                "tool": r"C:\rhwp-0.8.6\rhwp\rhwp.exe",
                "soffice": False,
                "pdf": str(pdf),
            }
        ),
        encoding="utf-8",
    )
    claim = l050_mechanization_status(evidence)
    assert claim["mechanized"] is False
    if sys.platform == "win32":
        assert claim["status"] == "GENERATED"
    else:
        assert claim["status"] == "BLOCKED"
    monkeypatch.setattr(gates.sys, "platform", "linux")
    ignored = l050_mechanization_status(evidence)
    assert ignored["status"] == "BLOCKED"
    assert ignored["mechanized"] is False
    monkeypatch.setattr(gates.sys, "platform", "win32")
    promoted = l050_mechanization_status(evidence)
    assert promoted["status"] == "GENERATED"
    assert promoted["mechanized"] is False
    assert l050_mechanization_status(None)["status"] == "BLOCKED"
    assert _lesson("L050")["category"] == "gap"


def test_win32_export_writes_evidence_but_not_mechanized(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "rhwp.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("RHWP_EXE", str(exe))
    monkeypatch.setattr(gates.sys, "platform", "win32")
    monkeypatch.setattr(gates.subprocess, "run", _fake_run(b"%PDF-1.4"))
    src = tmp_path / "신청서.hwpx"
    src.write_bytes(b"PK")
    gen = try_generate_sibling_pdf(src)
    assert gen.generated is True
    evidence = Path(gen.evidence)
    assert evidence.name == "신청서.l050.json"
    claim = l050_mechanization_status(evidence)
    assert claim["status"] == "GENERATED"
    assert claim["mechanized"] is False
    assert _lesson("L050")["category"] == "gap"


def test_l005_linux_stays_blocked_even_with_screenshot(tmp_path: Path, monkeypatch) -> None:
    assert _lesson("L005")["category"] == "judgment"
    shot = tmp_path / "screen.png"
    shot.write_bytes(b"\x89PNG\r\nnot-a-hangul-pixel-review")
    packet = tmp_path / "packet"
    status = record_l005_pixel_review(
        packet,
        document=tmp_path / "신청서.hwpx",
        checklist={key: True for key in L005_CHECKLIST},
        screenshot=shot,
    )
    assert status["logic_review_is_verification"] is False
    assert status["pytest_pass_counts"] is False
    assert status["status"] == l005_pixel_review_status(packet)["status"]
    if sys.platform != "win32":
        assert status["status"] == "BLOCKED"
    elif hangul_gui_available():
        assert status["status"] == "PASS"
    else:
        assert status["status"] == "NEEDS_HANGUL_GUI"
    monkeypatch.setattr(gates.sys, "platform", "linux")
    blocked = l005_pixel_review_status(packet)
    assert blocked["status"] == "BLOCKED"
    assert blocked["logic_review_is_verification"] is False
    assert blocked["pytest_pass_counts"] is False


def test_l005_template_and_incomplete_packet_are_not_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(gates.sys, "platform", "win32")
    monkeypatch.setattr(gates, "hangul_gui_available", lambda: True)
    template = write_l005_review_template(tmp_path / "blank", document="신청서.hwpx")
    data = json.loads(template.read_text(encoding="utf-8"))
    assert data["checklist"] == {key: False for key in L005_CHECKLIST}
    assert l005_pixel_review_status(tmp_path / "blank")["status"] == "REVIEW_REQUIRED"
    assert l005_pixel_review_status()["status"] == "REVIEW_REQUIRED"

    shot = tmp_path / "screen.png"
    shot.write_bytes(b"\x89PNG\r\npartial")
    partial = {key: True for key in L005_CHECKLIST}
    partial["image_size"] = False
    status = record_l005_pixel_review(
        tmp_path / "partial",
        document="신청서.hwpx",
        checklist=partial,
        screenshot=shot,
    )
    assert status["status"] == "REVIEW_REQUIRED"
    assert status["status"] != "PASS"


def test_l005_pass_requires_hangul_checklist_and_screenshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(gates.sys, "platform", "win32")
    monkeypatch.setattr(gates, "hangul_gui_available", lambda: False)
    shot = tmp_path / "screen.png"
    shot.write_bytes(b"\x89PNG\r\nchecklist-only")
    folder = tmp_path / "ready"
    missing_gui = record_l005_pixel_review(
        folder,
        document="신청서.hwpx",
        checklist={key: True for key in L005_CHECKLIST},
        screenshot=shot,
    )
    assert missing_gui["status"] == "NEEDS_HANGUL_GUI"
    monkeypatch.setattr(gates, "hangul_gui_available", lambda: True)
    ready = l005_pixel_review_status(folder)
    assert ready["status"] == "PASS"
    assert ready["logic_review_is_verification"] is False
    assert Path(ready["screenshot"]).is_file()
    assert _lesson("L005")["category"] == "judgment"

    cheated = json.loads((folder / "l005_checklist.json").read_text(encoding="utf-8"))
    cheated["pytest_pass_counts"] = True
    (folder / "l005_checklist.json").write_text(json.dumps(cheated), encoding="utf-8")
    assert l005_pixel_review_status(folder)["status"] == "REVIEW_REQUIRED"


def test_empty_screenshot_cannot_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(gates.sys, "platform", "win32")
    monkeypatch.setattr(gates, "hangul_gui_available", lambda: True)
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    status = record_l005_pixel_review(
        tmp_path / "empty",
        document="신청서.hwpx",
        checklist={key: True for key in L005_CHECKLIST},
        screenshot=empty,
    )
    assert status["status"] == "REVIEW_REQUIRED"


def test_submit_hwpx_attempts_sibling_pdf_only_when_submittable(tmp_path: Path, monkeypatch) -> None:
    _hide_rhwp(monkeypatch)
    calls: list[Path] = []

    def spy(path):
        calls.append(Path(path))
        return {
            "generated": False,
            "skipped": False,
            "blocked": True,
            "reason": "BLOCKED: spy",
            "evidence": "",
            "missing": True,
            "mechanized": False,
            "claim_status": "BLOCKED",
        }

    monkeypatch.setattr("auto_write.services.submission_gates.sibling_pdf_attempt", spy)
    source = _make_hwpx(tmp_path / "ok.hwpx")
    requested = tmp_path / "result.hwpx"
    report = hs.submit_hwpx(source, requested, identity={"기업명": "테스트기업"})
    assert report.submittable is True
    assert calls == [requested]
    assert report.pdf_pair["mechanized"] is False
    assert report.pdf_pair["claim_status"] == "BLOCKED"
    # submit_hwpx does not record a screenshot, so L005 cannot be PASS.
    live_l005 = l005_pixel_review_status()
    assert live_l005["status"] != "PASS"
    assert live_l005["logic_review_is_verification"] is False
    assert report.l005_review["status"] == live_l005["status"]
    assert report.l005_review["logic_review_is_verification"] is False
    assert not (tmp_path / "result.pdf").exists()

    calls.clear()
    invalid = _make_hwpx(tmp_path / "bad.hwpx", r9_invalid=True)
    blocked = hs.submit_hwpx(
        invalid,
        tmp_path / "blocked.hwpx",
        identity={"기업명": "테스트기업"},
        normalize_colors=False,
        submission_cleanup=False,
    )
    assert blocked.submittable is False
    assert calls == []
    assert blocked.l005_review["status"] == live_l005["status"]
    assert blocked.l005_review["status"] != "PASS"
    assert blocked.l005_review["logic_review_is_verification"] is False


def test_document_pdf_uses_rhwp_exe(tmp_path: Path, monkeypatch) -> None:
    from auto_write.image_automation import document_pdf as dp

    exe = tmp_path / "rhwp.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setenv("RHWP_EXE", str(exe))
    src = tmp_path / "in.hwpx"
    src.write_bytes(b"PK")
    dest = tmp_path / "out" / "normalized.pdf"
    calls: list[list[str]] = []

    def run(cmd, **_kwargs):
        calls.append(list(cmd))
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"%PDF-1.4")

        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return Proc()

    monkeypatch.setattr(dp.subprocess, "run", run)
    monkeypatch.setattr(dp, "validate_pdf", lambda _path: 1)
    dp.convert_hwp_family_to_pdf(src, dest)
    assert calls[0][0] == str(exe)
    assert calls[0][1:4] == ["export-pdf", str(src.resolve()), "-o"]


def test_com_pdf_not_used_when_rhwp_missing_on_windows(tmp_path: Path, monkeypatch) -> None:
    _hide_rhwp(monkeypatch)
    monkeypatch.setattr(gates.sys, "platform", "win32")
    src = tmp_path / "신청서.docx"
    src.write_bytes(b"PK")
    called: list = []
    monkeypatch.setattr(gates.subprocess, "run", lambda *args, **kwargs: called.append(args))
    gen = try_generate_sibling_pdf(src)
    assert called == []
    assert gen.generated is False
    assert gen.blocked is True
    assert "미배선" in gen.reason
    assert "RHWP_EXE" in gen.reason
