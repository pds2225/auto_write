"""닫힌 PR #186의 미반영 검사 강화와 보존된 호환 경로 회귀."""
import hashlib
import json
from pathlib import Path

import pytest

from auto_write.domains.domain_classifier import Domain
from auto_write.services.finalizer import finalize_artifact
from auto_write.services.lrule_enforcer import enforce_lrules


def _report(tmp_path, guard, *, total=1, report_path=None):
    artifact = tmp_path / "artifact.docx"
    artifact.write_bytes(b"controlled synthetic artifact")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "counts": {"total": total, "mechanized": 1, "gap": 0, "judgment": 0},
        "lessons": [{"id": "L001 | synthetic", "summary": "synthetic rule",
                     "domain": "all", "category": "mechanized", "guard_ref": "synthetic"}],
    }), encoding="utf-8")
    report = enforce_lrules(Domain.BUSINESS_PLAN, artifact_path=artifact,
                            lessons_path=registry, guards={"L001": guard},
                            report_path=report_path)
    return artifact, report


@pytest.mark.parametrize("guard", [
    {"passed": True, "evidence": ""},
    {"passed": "true", "evidence": "synthetic"},
    {"status": "PASS", "evidence": ""},
    {"status": "N/A", "reason": ""},
    {"status": "USER_OVERRIDE", "evidence": "synthetic", "user_approved": False},
    {"status": "USER_OVERRIDE", "evidence": "synthetic", "user_approved": "false"},
    {"status": "USER_OVERRIDE", "evidence": "synthetic", "user_approved": 1},
    {"status": "PASS", "passed": False, "evidence": "failed synthetic proof"},
    {"status": "UNKNOWN", "evidence": "synthetic"},
    True,
])
def test_unproven_guard_cannot_finalize(tmp_path, guard):
    artifact, report = _report(tmp_path, guard)
    assert not report.can_finalize
    assert not finalize_artifact(artifact, report).submittable


def test_callable_guard_exception_is_unverifiable(tmp_path):
    def unavailable(**context):
        raise OSError("synthetic guard failure")
    artifact, report = _report(tmp_path, unavailable)
    assert report.summary["unverifiable"] == 1
    assert not finalize_artifact(artifact, report).submittable


def test_short_code_proof_still_passes(tmp_path):
    artifact, report = _report(tmp_path, {"passed": True, "evidence": "controlled synthetic proof"})
    assert report.can_finalize
    assert finalize_artifact(artifact, report).submittable


def test_declared_missing_rule_blocks_final(tmp_path):
    artifact, report = _report(tmp_path, {"passed": True, "evidence": "synthetic proof"}, total=2)
    assert report.summary["missing"] == 1
    assert not finalize_artifact(artifact, report).submittable


def test_report_save_failure_blocks_final(tmp_path, monkeypatch):
    def unavailable(self, path):
        raise OSError("synthetic read-only report destination")
    monkeypatch.setattr("auto_write.services.lrule_enforcer.LRuleReport.save", unavailable)
    artifact, report = _report(tmp_path, {"passed": True, "evidence": "synthetic proof"},
                               report_path=tmp_path / "report.json")
    assert "save failed" in report.finalization_blocked_reason
    assert not finalize_artifact(artifact, report).submittable


@pytest.mark.parametrize("mutation", ["empty_evidence", "false_summary", "missing_registry"])
def test_finalizer_rechecks_entries_and_registry(tmp_path, mutation):
    artifact, report = _report(tmp_path, {"passed": True, "evidence": "synthetic proof"})
    if mutation == "empty_evidence":
        report.rules[0]["evidence"] = ""
    elif mutation == "false_summary":
        report.rules[0]["status"] = "FAIL"
    else:
        report.registry_sha256 = ""
    assert not finalize_artifact(artifact, report).submittable


def test_legacy_acceptance_patch_reaches_actual_pipeline(monkeypatch):
    from auto_write.services import autopilot_pipeline as legacy
    from core.docx.services import autopilot_pipeline as canonical
    marker = object()
    monkeypatch.setattr(legacy, "run_acceptance", marker)
    assert canonical.run_autopilot.__globals__["run_acceptance"] is marker


def test_hwpx_report_save_failure_keeps_only_draft(tmp_path, monkeypatch):
    from auto_write.domains.pipeline_gate import PipelineGateResult
    from auto_write.services import hwpx_submit
    artifact, lrule = _report(tmp_path, {"passed": True, "evidence": "synthetic proof"})
    output = tmp_path / "filled.hwpx"
    output.write_bytes(artifact.read_bytes())
    gate = PipelineGateResult(lrule_report=lrule, finalizer=finalize_artifact(artifact, lrule))
    monkeypatch.setattr("auto_write.domains.pipeline_gate.run_to_final", lambda *a, **k: gate)
    def unavailable(self, path):
        raise OSError("synthetic read-only report destination")
    monkeypatch.setattr("auto_write.services.lrule_enforcer.LRuleReport.save", unavailable)
    report = hwpx_submit.SubmitReport(input=str(artifact), final=str(output), ok=True,
                                     submittable=True, final_output_allowed=True)
    original = hashlib.sha256(artifact.read_bytes()).hexdigest()
    hwpx_submit._apply_lrule_gate(report)
    assert not report.ok and not report.submittable and not report.final_output_allowed
    assert not output.exists()
    assert Path(report.final).exists() and "_DRAFT" in Path(report.final).stem
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == original
