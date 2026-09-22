"""Resume production finalizer gate.

The consultant/resume entry must call the existing DomainRouter,
ConsultantApplicationPipeline, LRule enforcer, and finalizer.
Ambiguous domain and any blocking LRule stay _DRAFT.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from auto_write.domains.domain_classifier import Domain
from auto_write.services.lrule_enforcer import (
    LRuleEnforcer,
    LRuleReport,
    compute_registry_sha256,
    compute_sha256,
    enforce_lrules,
)
from resume.pipeline import finalize_consultant_resume

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _hwpx(path: Path) -> Path:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}"/>'
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w") as zipped:
        zipped.writestr("mimetype", b"application/hwp+zip")
        zipped.writestr("Contents/section0.xml", xml)
    return path


def _registry() -> tuple[str, str]:
    lessons = LRuleEnforcer().lessons_path
    return str(lessons), compute_registry_sha256(lessons)


def _report(
    artifact: Path,
    *,
    domain: str,
    status: str | None = None,
    can_finalize: bool = False,
    reason: str = "",
    save: bool = True,
) -> LRuleReport:
    registry_path, registry_sha = _registry()
    summary = {
        "total": 1 if status else 0,
        "pass": 0,
        "na": 0,
        "fail": 0,
        "review_required": 0,
        "unverifiable": 0,
        "user_override": 0,
    }
    rules: list[dict] = []
    if status == "FAIL":
        summary["fail"] = 1
        rules.append({
            "id": "L-SYNTH",
            "status": "FAIL",
            "evidence": "synthetic fixture failed",
            "reason": "synthetic FAIL",
            "reviewer": "auto",
        })
    elif status == "REVIEW_REQUIRED":
        summary["review_required"] = 1
        rules.append({
            "id": "L-SYNTH",
            "status": "REVIEW_REQUIRED",
            "evidence": "",
            "reason": "synthetic REVIEW_REQUIRED",
            "reviewer": "auto",
        })
    elif status == "UNVERIFIABLE":
        summary["unverifiable"] = 1
        rules.append({
            "id": "L-SYNTH",
            "status": "UNVERIFIABLE",
            "evidence": "",
            "reason": "synthetic UNVERIFIABLE",
            "reviewer": "auto",
        })
    elif status == "PASS":
        summary["pass"] = 1
        rules.append({
            "id": "L-SYNTH",
            "status": "PASS",
            "evidence": "synthetic controlled-pass evidence",
            "reason": "",
            "reviewer": "auto",
        })
    report = LRuleReport(
        domain=domain,
        document_type="resume",
        artifact_path=str(artifact),
        artifact_sha256=compute_sha256(artifact),
        registry_sha256=registry_sha,
        registry_path=registry_path,
        summary=summary,
        rules=rules,
        can_finalize=can_finalize,
        finalization_blocked_reason=reason,
    )
    if save:
        report.save(artifact.with_name(f"{artifact.stem}_lrule_report.json"))
    return report


def _assert_draft(result, artifact: Path) -> None:
    final = Path(result.final_path)
    assert result.is_draft
    assert not result.submittable
    assert final.exists()
    assert "_DRAFT" in final.stem
    assert not artifact.exists()
    assert final.resolve() != artifact.resolve()


def test_ambiguous_domain_is_not_final(tmp_path: Path) -> None:
    artifact = _hwpx(tmp_path / "note.hwpx")
    result = finalize_consultant_resume(
        artifact,
        text="no domain signal",
        filename="note.txt",
    )
    _assert_draft(result, artifact)
    assert "ambiguous or unsupported domain" in result.blocked_reason


def test_ambiguous_domain_is_not_rewritten_when_report_would_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _hwpx(tmp_path / "note.hwpx")
    seen: dict[str, Domain] = {}

    def _passing(domain, **kwargs):
        seen["domain"] = domain
        return _report(
            artifact,
            domain=domain.value,
            status="PASS",
            can_finalize=True,
            save=True,
        )

    monkeypatch.setattr("resume.pipeline.enforce_lrules", _passing)
    result = finalize_consultant_resume(
        artifact,
        text="zzzz",
        filename="plain.txt",
    )
    assert seen["domain"] == Domain.OTHER
    _assert_draft(result, artifact)
    assert "ambiguous or unsupported domain" in result.blocked_reason


@pytest.mark.parametrize("status", ["FAIL", "REVIEW_REQUIRED", "UNVERIFIABLE"])
def test_blocking_lrule_status_is_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str,
) -> None:
    artifact = _hwpx(tmp_path / "resume.hwpx")

    def _blocked(domain, **kwargs):
        return _report(
            artifact,
            domain=Domain.CONSULTANT_APPLICATION.value,
            status=status,
            can_finalize=True,
            save=True,
        )

    monkeypatch.setattr("resume.pipeline.enforce_lrules", _blocked)
    result = finalize_consultant_resume(
        artifact,
        text="이력서 경력 자격",
        filename="이력서.hwpx",
        document_type="resume",
    )
    _assert_draft(result, artifact)
    assert status in result.blocked_reason or status.replace("_", " ") in result.blocked_reason


def test_missing_report_file_is_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _hwpx(tmp_path / "resume.hwpx")

    def _unsaved(domain, **kwargs):
        return _report(
            artifact,
            domain=Domain.CONSULTANT_APPLICATION.value,
            status="PASS",
            can_finalize=True,
            save=False,
        )

    monkeypatch.setattr("resume.pipeline.enforce_lrules", _unsaved)
    result = finalize_consultant_resume(
        artifact,
        document_type="resume",
        filename="이력서_경력.hwpx",
    )
    _assert_draft(result, artifact)
    assert "missing lrule report" in result.blocked_reason


def test_enforce_exception_is_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _hwpx(tmp_path / "resume.hwpx")

    def _boom(*args, **kwargs):
        raise RuntimeError("registry unreadable")

    monkeypatch.setattr("resume.pipeline.enforce_lrules", _boom)
    result = finalize_consultant_resume(artifact, document_type="resume")
    _assert_draft(result, artifact)
    assert "missing lrule report" in result.blocked_reason


def test_controlled_pass_can_finalize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _hwpx(tmp_path / "resume.hwpx")
    enforcer = LRuleEnforcer()
    guards = {
        lesson["id"]: {
            "passed": True,
            "evidence": "synthetic controlled-pass evidence",
        }
        for lesson in enforcer._lessons
        if lesson.get("id")
    }

    def _pass_all(domain, **kwargs):
        kwargs = dict(kwargs)
        kwargs["guards"] = guards
        return enforce_lrules(domain, **kwargs)

    monkeypatch.setattr("resume.pipeline.enforce_lrules", _pass_all)
    result = finalize_consultant_resume(
        artifact,
        document_type="resume",
        filename="이력서.hwpx",
    )
    final = Path(result.final_path)
    assert result.submittable
    assert not result.is_draft
    assert final.exists()
    assert "_DRAFT" not in final.stem
    assert artifact.exists()


def test_cli_fill_uses_finalizer_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from resume_fill import main

    table = (
        '<hp:tbl rowCnt="1" colCnt="2"><hp:tr>'
        '<hp:tc><hp:cellAddr colAddr="0" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t>성명</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '<hp:tc><hp:cellAddr colAddr="1" rowAddr="0"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        '<hp:subList><hp:p><hp:run charPrIDRef="0"><hp:t></hp:t></hp:run></hp:p></hp:subList></hp:tc>'
        '</hp:tr></hp:tbl>'
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        f'<hp:p><hp:run charPrIDRef="0">{table}</hp:run></hp:p>'
        '</hs:sec>'
    ).encode("utf-8")
    artifact_form = tmp_path / "form.hwpx"
    with zipfile.ZipFile(artifact_form, "w") as zipped:
        zipped.writestr("mimetype", b"application/hwp+zip")
        zipped.writestr("Contents/header.xml", b'<?xml version="1.0"?><hh:head xmlns:hh="x">FONTS</hh:head>')
        zipped.writestr("Contents/section0.xml", body)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"identity": {"name": "홍길동"}}), encoding="utf-8")
    out = tmp_path / "out.hwpx"
    called: dict[str, Path] = {}

    def _gate(path, **kwargs):
        called["path"] = Path(path)
        return type("Gate", (), {
            "final_path": str(path),
            "submittable": True,
            "blocked_reason": "",
            "is_draft": False,
        })()

    monkeypatch.setattr("resume.pipeline.finalize_consultant_resume", _gate)
    rc = main(["fill", str(artifact_form), "--profile", str(profile), "-o", str(out)])
    assert rc == 0
    assert called["path"] == out
    assert out.exists()
