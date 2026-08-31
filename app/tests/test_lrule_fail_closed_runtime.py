"""Runtime fail-closed regression tests for LRule reports and finalization."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from auto_write.domains.domain_classifier import Domain
from auto_write.services.finalizer import finalize_artifact
from auto_write.services.lrule_enforcer import LRuleEnforcer, enforce_lrules


def _artifact(tmp_path: Path) -> Path:
    path = tmp_path / "artifact.docx"
    path.write_bytes(b"synthetic artifact")
    return path


def _registry() -> Path:
    return Path(__file__).with_name("lessons_coverage.json")


def test_runtime_report_is_persisted_and_artifact_mutation_blocks_final(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    report_path = tmp_path / "lrule_report.json"
    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        report_path=report_path,
    )

    assert report.report_path == str(report_path)
    assert report_path.exists()
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["artifact_sha256"] == report.artifact_sha256

    artifact.write_bytes(b"mutated after lrule report")
    result = finalize_artifact(artifact, report)
    assert result.is_draft
    assert not result.submittable
    assert "artifact SHA256 mismatch" in result.blocked_reason


def test_registry_mutation_blocks_finalization(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    shutil.copy2(_registry(), registry)
    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        report_path=tmp_path / "lrule_report.json",
    )

    registry.write_bytes(registry.read_bytes() + b"\n")
    result = finalize_artifact(artifact, report)
    assert result.is_draft
    assert "registry SHA256 mismatch" in result.blocked_reason


def test_pass_without_evidence_is_not_pass(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    enforcer = LRuleEnforcer()
    rule_id = next(item["id"] for item in enforcer._lessons if item.get("category") == "mechanized")
    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        guards={rule_id: {"passed": True}},
        save_report=False,
    )

    entry = next(item for item in report.rules if item["id"] == rule_id)
    assert entry["status"] == "REVIEW_REQUIRED"
    assert "evidence" in entry["reason"]


def test_duplicate_registry_is_reported_and_blocks_final(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    data = json.loads(_registry().read_text(encoding="utf-8"))
    data["lessons"].append(dict(data["lessons"][0]))
    registry.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        save_report=False,
    )
    assert report.summary["duplicate"] > 0
    assert not report.can_finalize


def test_report_save_failure_is_fail_closed(tmp_path: Path, monkeypatch) -> None:
    artifact = _artifact(tmp_path)

    def fail_save(self, path):
        raise OSError("read-only report destination")

    monkeypatch.setattr("auto_write.services.lrule_enforcer.LRuleReport.save", fail_save)
    report = enforce_lrules(Domain.BUSINESS_PLAN, artifact_path=artifact)
    assert not report.can_finalize
    assert "lrule report save failed" in report.finalization_blocked_reason


def test_other_domain_cannot_be_finalized(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    report = enforce_lrules(Domain.OTHER, artifact_path=artifact, save_report=False)
    result = finalize_artifact(artifact, report)
    assert result.is_draft
    assert not result.submittable
    assert "ambiguous or unsupported domain" in result.blocked_reason


def test_materialized_draft_has_a_real_path(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    report = enforce_lrules(Domain.BUSINESS_PLAN, artifact_path=artifact, save_report=False)

    result = finalize_artifact(artifact, report, materialize=True)

    draft = Path(result.final_path)
    assert result.is_draft
    assert draft.exists()
    assert not artifact.exists()


def test_materialized_final_copy_uses_finalizer_output_path(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    enforcer = LRuleEnforcer()
    guards = {
        lesson["id"]: {"passed": True, "evidence": "synthetic controlled-pass evidence"}
        for lesson in enforcer._lessons
    }
    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        guards=guards,
        save_report=False,
    )
    assert report.can_finalize

    final_path = tmp_path / "submission.docx"
    result = finalize_artifact(
        artifact,
        report,
        output_path=final_path,
        materialize=True,
    )

    assert result.submittable
    assert final_path.exists()
    assert artifact.exists()
    assert final_path.read_bytes() == artifact.read_bytes()
