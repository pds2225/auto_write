# -*- coding: utf-8 -*-
"""Hancom reopen/render gate.

채운 HWPX가 ZIP·섹션 XML·content.hpf 바인딩을 유지하는지,
rhwp가 없을 때 repair/렌더를 명시적으로 건너뛰는지,
한컴 COM 2024(HOffice130)가 기본 차단되는지 잠근다.

L005 한글 GUI 픽셀과 L050 동일명 PDF는 이 클라우드에서 PASS가 아니다.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from auto_write.services.hwpx_integrity_gate import REVIEW_REQUIRED, run_hwpx_integrity_gate
from auto_write.services.hwpx_submit import (
    RHWP_ABSENT_RENDER_NOTE,
    RHWP_ABSENT_REPAIR_NOTE,
    RHWP_DISABLED_RENDER_NOTE,
    XML_OVERFLOW_NOT_L005_NOTE,
    submit_hwpx,
)
from core.docx.services import hancom_com_guard as guard
from core.docx.services import native_hwp
from core.docx.services.hancom_com_guard import HancomComGuardError, HancomComSnapshot

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_MIMETYPE = b"application/hwp+zip"
_HPF = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
    '<opf:manifest><opf:item id="section0" href="Contents/section0.xml" '
    'media-type="application/xml"/></opf:manifest>'
    '<opf:spine><opf:itemref idref="section0"/></opf:spine>'
    "</opf:package>"
).encode("utf-8")
_BLOB = b"PNGDATA-BINDING-KEEP"
_FILL = "보존기업"
_SIGNATURE = "김보존(인)"
_CHECKBOX = "□ 제조"
_EXISTING = "밸류업파트너스"
_DATE = "2020-03-01"


def _header() -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hh:head xmlns:hh="{_HH}"><hh:refList><hh:charProperties itemCnt="1">'
        '<hh:charPr id="0" textColor="000000"/>'
        "</hh:charProperties></hh:refList></hh:head>"
    ).encode("utf-8")


def _cell(col: int, row: int, text: str) -> str:
    return (
        f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0">'
        f"<hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>"
    )


def _row(row: int, label: str, value: str) -> str:
    return f"<hp:tr>{_cell(0, row, label)}{_cell(1, row, value)}</hp:tr>"


def _section_clean() -> bytes:
    rows = "".join([_row(0, "상호", ""), _row(1, "대표자", _EXISTING)])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="2">{rows}'
        "</hp:tbl></hp:run></hp:p></hs:sec>"
    ).encode("utf-8")


def _section_protected_broken() -> bytes:
    """주소가 겹친 표 + 서명/체크 텍스트. repair는 주소만 고쳐야 한다."""
    broken = "".join(
        [
            f"<hp:tr>{_cell(0, 0, '상호')}{_cell(1, 0, '')}</hp:tr>",
            f"<hp:tr>{_cell(0, 1, '서명')}{_cell(1, 1, _SIGNATURE)}</hp:tr>",
            f"<hp:tr>{_cell(0, 1, '선택')}{_cell(1, 1, _CHECKBOX)}</hp:tr>",
        ]
    )
    kept = "".join([_row(0, "대표자", _EXISTING), _row(1, "일자", _DATE)])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="3" colCnt="2">{broken}'
        "</hp:tbl></hp:run></hp:p>"
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="2" colCnt="2">{kept}'
        "</hp:tbl></hp:run></hp:p></hs:sec>"
    ).encode("utf-8")


def _section_overflow() -> bytes:
    cell = (
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:cellSz width="100" height="10"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>상호</hp:t>'
        "</hp:run></hp:p></hp:subList></hp:tc>"
        '<hp:tc><hp:cellAddr colAddr="1" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:cellSz width="100" height="10"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t></hp:t>'
        "</hp:run></hp:p></hp:subList></hp:tc>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0"><hp:tbl rowCnt="1" colCnt="2">'
        f"<hp:tr>{cell}</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>"
    ).encode("utf-8")


def _write(path: Path, section: bytes, *, colored: bool = False) -> None:
    header = _header()
    if colored:
        header = header.replace(b'textColor="000000"', b'textColor="FF0000"')
    with zipfile.ZipFile(path, "w") as z:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, _MIMETYPE)
        z.writestr("Contents/header.xml", header)
        z.writestr("Contents/section0.xml", section)
        z.writestr("Contents/content.hpf", _HPF)
        z.writestr("BinData/pic.bin", _BLOB)
        z.writestr("Contents/version.xml", b"<version>keep</version>")


def _assert_package(path: Path, *texts: str) -> str:
    assert path.is_file(), path
    assert zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert names[0] == "mimetype"
        assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype") == _MIMETYPE
        assert "Contents/section0.xml" in names
        section = z.read("Contents/section0.xml")
        etree.fromstring(section)
        assert z.read("Contents/content.hpf") == _HPF
        assert b'idref="section0"' in z.read("Contents/content.hpf")
        assert z.read("BinData/pic.bin") == _BLOB
        assert z.read("Contents/version.xml") == b"<version>keep</version>"
    decoded = section.decode("utf-8")
    for text in texts:
        assert text in decoded
    return decoded


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _no_leftovers(folder: Path) -> None:
    names = [path.name for path in folder.iterdir()]
    assert not any(name.endswith(".tmp") for name in names)
    assert not any("__grid_repair__" in name or "__cleanup__" in name or "__t02_auth__" in name for name in names)
    assert not any(name.endswith(".pdf") for name in names)


def _force_rhwp_absent(monkeypatch) -> None:
    monkeypatch.delenv("AUTO_WRITE_ENABLE_RHWP", raising=False)
    monkeypatch.delenv("RHWP_EXE", raising=False)
    monkeypatch.setattr(native_hwp, "rhwp_available", lambda: False)

    def _which(name: str):
        if name == "rhwp":
            return None
        return None

    monkeypatch.setattr(native_hwp.shutil, "which", _which)


def test_filled_package_keeps_zip_members_section_and_spine_binding(tmp_path, monkeypatch):
    _force_rhwp_absent(monkeypatch)
    src = tmp_path / "form.hwpx"
    _write(src, _section_clean())
    before = _sha(src)
    out = tmp_path / "out.hwpx"

    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": _FILL},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert _sha(src) == before
    assert rep.ok is True
    assert rep.submittable is True
    assert Path(rep.final) == out
    _assert_package(out, _FILL, _EXISTING)
    assert rep.native_render.get("render_status") == "NOT_RUN"
    assert rep.native_render.get("reopen_status") == "NOT_RUN"
    assert rep.native_render.get("l005_pixel") == "NOT_RUN"
    assert rep.native_render.get("l050_pdf") == "NOT_RUN"
    assert rep.native_render.get("disabled") is True
    assert rep.native_render.get("pixel_reopen_claimed") is False
    assert rep.native_render.get("ok") is False
    assert rep.native_render.get("severity") == "PASS"
    assert RHWP_DISABLED_RENDER_NOTE in rep.notes
    assert rep.integrity["final_status"] == "PASS"
    render = next(v for v in rep.integrity["validators"] if v["source_validator"] == "rendering_validator")
    assert render["validator_status"] == "NOT_RUN"
    assert render["severity"] == "PASS"
    assert render["defect_code"] == "RHWP_DISABLED"
    _no_leftovers(tmp_path)


def test_same_path_refusal_preserves_source_sha_and_writes_nothing(tmp_path):
    src = tmp_path / "form.hwpx"
    _write(src, _section_clean())
    before = _sha(src)
    names = sorted(path.name for path in tmp_path.iterdir())

    with pytest.raises(ValueError, match="덮어쓰기"):
        submit_hwpx(src, src, identity={"기업명": _FILL}, preserve_template=True)

    assert _sha(src) == before
    assert sorted(path.name for path in tmp_path.iterdir()) == names
    _assert_package(src)


def test_acceptance_fail_leaves_one_valid_draft_and_source_sha(tmp_path, monkeypatch):
    """양식에 있던 유색은 결함이 아니다. 잔여 더미명(홍길동)만 초안을 남긴다."""
    _force_rhwp_absent(monkeypatch)
    src = tmp_path / "colored.hwpx"
    section = _section_clean().replace(
        b"</hs:sec>",
        (
            '<hp:p><hp:run charPrIDRef="0"><hp:t>참고 홍길동</hp:t></hp:run></hp:p>'
            "</hs:sec>"
        ).encode("utf-8"),
    )
    _write(src, section, colored=True)
    before = _sha(src)
    out = tmp_path / "out.hwpx"

    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": _FILL},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert _sha(src) == before
    assert rep.ok is False
    assert rep.submittable is False
    final = Path(rep.final)
    assert final.name == "out_DRAFT.hwpx"
    assert not out.exists()
    _assert_package(final, _FILL, _EXISTING)
    assert rep.native_render.get("l005_pixel") != "PASS"
    assert rep.native_render.get("l050_pdf") != "PASS"
    _no_leftovers(tmp_path)


def test_rhwp_absent_skips_grid_repair_without_corrupting_package(tmp_path, monkeypatch):
    _force_rhwp_absent(monkeypatch)
    monkeypatch.setenv("AUTO_WRITE_ENABLE_RHWP", "1")
    src = tmp_path / "broken.hwpx"
    _write(src, _section_protected_broken())
    before = _sha(src)
    out = tmp_path / "out.hwpx"

    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": _FILL},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert _sha(src) == before
    assert rep.ok is False
    assert rep.repair == {}
    assert RHWP_ABSENT_REPAIR_NOTE in rep.notes
    assert RHWP_ABSENT_RENDER_NOTE in rep.notes
    assert rep.native_render.get("reopen_status") == "NOT_RUN"
    assert rep.native_render.get("l005_pixel") == "ENV_BLOCKED"
    final = Path(rep.final)
    assert final.name == "out_DRAFT.hwpx"
    section = _assert_package(final, _FILL, _SIGNATURE, _CHECKBOX, _EXISTING, _DATE)
    assert 'rowAddr="2"' not in section
    assert rep.semantic_after.get("ok") is False
    _no_leftovers(tmp_path)


def test_rhwp_present_repairs_grid_without_wiping_protected_text(tmp_path, monkeypatch):
    monkeypatch.setattr(native_hwp, "rhwp_available", lambda: True)

    def _review(path: str) -> dict:
        assert Path(path).is_file()
        return {
            "ok": False,
            "severity": "REVIEW_REQUIRED",
            "renderer": "rhwp",
            "render_status": "PASS",
            "reopen_status": "PASS",
            "visual_review": "NOT_RUN",
            "l005_pixel": "JUDGMENT",
            "l050_pdf": "NOT_SIBLING",
            "pixel_reopen_claimed": False,
            "message": "rhwp info only — not a Hangul GUI pixel pass",
            "pdf": "",
            "page_count": 1,
        }

    monkeypatch.setattr(native_hwp, "verify_hwpx_native", _review)
    src = tmp_path / "broken.hwpx"
    _write(src, _section_protected_broken())
    before = _sha(src)
    out = tmp_path / "out.hwpx"

    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": _FILL},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )

    assert _sha(src) == before
    assert rep.repair.get("grid_cells_fixed", 0) > 0
    assert rep.semantic_after.get("ok") is True
    assert rep.semantic_after.get("broken_tables") == []
    assert rep.native_render.get("l005_pixel") == "JUDGMENT"
    assert rep.native_render.get("l050_pdf") == "NOT_SIBLING"
    assert rep.native_render.get("pixel_reopen_claimed") is False
    assert rep.ok is False
    assert rep.submittable is False
    section = _assert_package(Path(rep.final), _FILL, _SIGNATURE, _CHECKBOX, _EXISTING, _DATE)
    assert 'rowAddr="2"' in section
    _no_leftovers(tmp_path)


def test_render_failure_stays_unsubmittable_and_package_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(native_hwp, "rhwp_available", lambda: True)

    def _fail(_path: str) -> dict:
        return {
            "ok": False,
            "severity": "REVIEW_REQUIRED",
            "renderer": "rhwp",
            "render_status": "FAIL",
            "reopen_status": "NOT_RUN",
            "visual_review": "NOT_RUN",
            "l005_pixel": "NOT_RUN",
            "l050_pdf": "NOT_RUN",
            "pixel_reopen_claimed": False,
            "message": "rhwp export failed",
            "pdf": "",
            "page_count": 0,
        }

    monkeypatch.setattr(native_hwp, "verify_hwpx_native", _fail)
    src = tmp_path / "form.hwpx"
    _write(src, _section_clean())
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        src, out, identity={"기업명": _FILL},
        normalize_colors=False, submission_cleanup=False, preserve_template=True,
    )
    assert rep.ok is False
    assert rep.submittable is False
    assert Path(rep.final).name == "out_DRAFT.hwpx"
    assert not out.exists()
    _assert_package(Path(rep.final), _FILL)
    assert rep.native_render.get("l005_pixel") != "PASS"
    _no_leftovers(tmp_path)


def test_unavailable_plus_pixel_pass_claim_is_rejected(tmp_path):
    src = tmp_path / "form.hwpx"
    _write(src, _section_clean())

    def _lie(_path: str) -> dict:
        return {
            "ok": True,
            "severity": "PASS",
            "render_status": "UNAVAILABLE",
            "reopen_status": "PASS",
            "l005_pixel": "PASS",
            "l050_pdf": "PASS",
            "pixel_reopen_claimed": True,
            "message": "should not count",
        }

    report = run_hwpx_integrity_gate(str(src), render_validator=_lie)
    assert report.final_status == REVIEW_REQUIRED
    render = next(v for v in report.validators if v.source_validator == "rendering_validator")
    assert render.validator_status == "ERROR"
    assert render.defect_code == "RENDER_CLAIM_WITHOUT_TOOL"
    assert render.severity == REVIEW_REQUIRED


def test_verify_success_does_not_set_l005_or_l050_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_WRITE_ENABLE_RHWP", "1")
    candidate = tmp_path / "candidate.hwpx"
    candidate.write_bytes(b"hwpx-bytes-for-hash")

    def _json(*args, **_kwargs):
        if args[0] == "info":
            return {"format": "hwpx", "pageCount": 1}
        pdf = Path(args[args.index("-o") + 1])
        pdf.write_bytes(b"%PDF-1.4\n")
        return {"format": "pdf", "pageCount": 1, "renderedCount": 1}

    class _Reader:
        pages = [object()]

    monkeypatch.setattr(native_hwp, "_rhwp_json", _json)
    monkeypatch.setattr("pypdf.PdfReader", lambda *_a, **_k: _Reader())
    evidence = native_hwp.verify_hwpx_native(candidate)
    assert evidence["render_status"] == "PASS"
    assert evidence["reopen_status"] == "PASS"
    assert evidence["l005_pixel"] == "JUDGMENT"
    assert evidence["l050_pdf"] == "NOT_SIBLING"
    assert evidence["visual_review"] == "NOT_RUN"
    assert evidence["pixel_reopen_claimed"] is False
    assert evidence["ok"] is False
    assert evidence["severity"] == "REVIEW_REQUIRED"
    assert "L005" in evidence["message"]
    assert not (tmp_path / "candidate.pdf").exists()


def test_default_rhwp_does_not_spawn_or_draft(tmp_path, monkeypatch):
    """설치된 rhwp 도 기본값은 실행하지 않고 NOT_RUN 이며 _DRAFT 사유가 아니다."""
    exe = tmp_path / "rhwp.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.delenv("AUTO_WRITE_ENABLE_RHWP", raising=False)
    monkeypatch.setenv("RHWP_EXE", str(exe))
    calls: list = []
    monkeypatch.setattr(
        native_hwp.subprocess,
        "run",
        lambda *args, **kwargs: calls.append(args),
    )
    assert native_hwp.rhwp_enabled() is False
    assert native_hwp.resolve_rhwp_executable() is None
    assert native_hwp.rhwp_available() is False
    candidate = tmp_path / "candidate.hwpx"
    candidate.write_bytes(b"PK")
    evidence = native_hwp.verify_hwpx_native(candidate)
    assert evidence["render_status"] == "NOT_RUN"
    assert evidence["reopen_status"] == "NOT_RUN"
    assert evidence["disabled"] is True
    assert evidence["severity"] == "PASS"
    assert evidence["l005_pixel"] == "NOT_RUN"
    assert "disabled" in evidence["message"]
    assert calls == []

    src = tmp_path / "form.hwpx"
    _write(src, _section_clean())
    out = tmp_path / "out.hwpx"
    rep = submit_hwpx(
        src,
        out,
        identity={"기업명": _FILL},
        normalize_colors=False,
        submission_cleanup=False,
        preserve_template=True,
    )
    assert rep.ok is True
    assert rep.submittable is True
    assert Path(rep.final) == out
    assert not (tmp_path / "out_DRAFT.hwpx").exists()
    assert rep.native_render.get("render_status") == "NOT_RUN"
    assert rep.native_render.get("severity") == "PASS"
    assert calls == []
    _no_leftovers(tmp_path)


def test_disabled_not_run_plus_pixel_pass_claim_is_rejected(tmp_path):
    src = tmp_path / "form.hwpx"
    _write(src, _section_clean())

    def _lie(_path: str) -> dict:
        payload = native_hwp._disabled_render_evidence()
        payload["reopen_status"] = "PASS"
        payload["l005_pixel"] = "PASS"
        return payload

    report = run_hwpx_integrity_gate(str(src), render_validator=_lie)
    assert report.final_status == REVIEW_REQUIRED
    render = next(v for v in report.validators if v.source_validator == "rendering_validator")
    assert render.validator_status == "ERROR"
    assert render.defect_code == "RENDER_CLAIM_WITHOUT_TOOL"
    assert render.severity == REVIEW_REQUIRED


def test_verify_absent_rhwp_is_env_blocked_not_reopen_pass(tmp_path, monkeypatch):
    _force_rhwp_absent(monkeypatch)
    monkeypatch.setenv("AUTO_WRITE_ENABLE_RHWP", "1")
    candidate = tmp_path / "candidate.hwpx"
    candidate.write_bytes(b"hwpx-bytes")
    evidence = native_hwp.verify_hwpx_native(candidate)
    assert evidence["render_status"] == "UNAVAILABLE"
    assert evidence["reopen_status"] == "NOT_RUN"
    assert evidence["l005_pixel"] == "ENV_BLOCKED"
    assert evidence["l050_pdf"] == "ENV_BLOCKED"
    assert evidence["pixel_reopen_claimed"] is False
    assert evidence["ok"] is False
    assert "rhwp 미설치" in evidence["message"]
    assert not list(tmp_path.glob("*.pdf"))


def test_xml_overflow_note_is_not_an_l005_pass(tmp_path, monkeypatch):
    _force_rhwp_absent(monkeypatch)
    src = tmp_path / "sized.hwpx"
    _write(src, _section_overflow())
    out = tmp_path / "out.hwpx"
    value = "아주 긴 입력값" * 20
    rep = submit_hwpx(
        src, out, identity={"기업명": value},
        normalize_colors=False, submission_cleanup=False, preserve_template=True,
    )
    assert rep.ok is True
    assert rep.routing_status == "LOCAL_LAYOUT_RISK"
    assert Path(rep.final) == out
    assert XML_OVERFLOW_NOT_L005_NOTE in rep.notes
    assert rep.native_render.get("l005_pixel") == "NOT_RUN"
    assert rep.native_render.get("render_status") == "NOT_RUN"
    assert rep.native_render.get("severity") == "PASS"
    render = next(v for v in rep.integrity["validators"] if v["source_validator"] == "rendering_validator")
    assert render["severity"] == "PASS"
    assert render["defect_code"] == "RHWP_DISABLED"
    assert rep.integrity["final_status"] == "REVIEW_REQUIRED"
    risk = next(v for v in rep.integrity["validators"] if v["source_validator"] == "fixed_cell_height_guard")
    assert risk["evidence"]["render_confirmed"] is False
    _assert_package(out, value)
    _no_leftovers(tmp_path)


def test_linux_com_guard_names_rhwp_only_path(monkeypatch):
    monkeypatch.setattr(guard.sys, "platform", "linux")
    with pytest.raises(HancomComGuardError, match="rhwp-hwpx-fill"):
        guard.assert_safe_hwp_com_or_raise()


def test_hoffice130_blocked_unless_explicit_env_opt_in(monkeypatch):
    snap = HancomComSnapshot(
        hwpframe_localserver32=r"C:\Hnc\Office 2024\HOffice130\Bin\Hwp.exe -Automation",
        hwp_document_130_localserver32=r"C:\Hnc\Office 2024\HOffice130\Bin\Hwp.exe",
        dot_hwp_progid="Hwp.Document.130",
        dot_hwpx_progid=None,
    )
    monkeypatch.setattr(guard.sys, "platform", "win32")
    monkeypatch.setattr(guard, "snapshot_hancom_com", lambda: snap)
    monkeypatch.delenv("AUTO_WRITE_ALLOW_HANCOM_2024_COM", raising=False)
    with pytest.raises(HancomComGuardError, match="HOffice130") as blocked:
        guard.assert_safe_hwp_com_or_raise()
    assert "rhwp-hwpx-fill" in str(blocked.value)
    monkeypatch.setenv("AUTO_WRITE_ALLOW_HANCOM_2024_COM", "0")
    with pytest.raises(HancomComGuardError, match="HOffice130"):
        guard.assert_safe_hwp_com_or_raise()
    monkeypatch.setenv("AUTO_WRITE_ALLOW_HANCOM_2024_COM", "1")
    allowed = guard.assert_safe_hwp_com_or_raise()
    assert allowed.hwpframe_is_2024 is True
    if sys.platform != "win32":
        from core.docx.services.submission_gates import l005_pixel_review_status

        status = l005_pixel_review_status()
        assert status["status"] == "BLOCKED"
        assert status["logic_review_is_verification"] is False
