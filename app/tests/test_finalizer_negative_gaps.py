"""FINAL negative cases that were not already asserted.

Already covered, and not repeated here:

- artifact bytes change after the LRule report → ``test_lrule_fail_closed_runtime.py``
- registry bytes change after the report → ``test_lrule_fail_closed_runtime.py``
- ``Domain.OTHER`` cannot finalize → ``test_lrule_fail_closed_runtime.py``

Duplicate rule ids already set ``can_finalize`` false in that same module.
This file asserts the Finalizer result for a duplicate-only registry, which
that test does not call.
"""
from __future__ import annotations

import json
from pathlib import Path

from auto_write.domains.domain_classifier import Domain
from auto_write.services.finalizer import finalize_artifact
from auto_write.services.lrule_enforcer import enforce_lrules

_PASS_EVIDENCE = "synthetic controlled-pass evidence"


def _artifact(tmp_path: Path, name: str = "artifact.docx") -> Path:
    path = tmp_path / name
    path.write_bytes(b"synthetic artifact")
    return path


def _lesson(rule_id: str, category: str, domain: str = "all") -> dict:
    return {
        "id": rule_id,
        "summary": f"synthetic {category} rule {rule_id}",
        "category": category,
        "domain": domain,
        "guard_ref": f"synthetic.{rule_id}",
    }


def _write_registry(path: Path, lessons: list[dict], *, total: int | None = None) -> None:
    counts = {
        "mechanized": sum(1 for lesson in lessons if lesson.get("category") == "mechanized"),
        "gap": sum(1 for lesson in lessons if lesson.get("category") == "gap"),
        "judgment": sum(1 for lesson in lessons if lesson.get("category") == "judgment"),
        "total": len(lessons) if total is None else total,
    }
    path.write_text(json.dumps({"counts": counts, "lessons": lessons}, ensure_ascii=False), encoding="utf-8")


def _passing_guard(rule_id: str) -> dict:
    return {rule_id: {"passed": True, "evidence": _PASS_EVIDENCE}}


def test_missing_mechanized_guard_is_unverifiable_and_blocks_final(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    _write_registry(registry, [_lesson("L-MECH", "mechanized")])

    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        guards={},
        save_report=False,
    )

    entry = report.rules[0]
    assert entry["id"] == "L-MECH"
    assert entry["status"] == "UNVERIFIABLE"
    assert entry["evidence"] == ""
    assert "no callable provided" in entry["reason"]
    assert report.summary["unverifiable"] == 1
    assert report.can_finalize is False

    result = finalize_artifact(artifact, report)
    assert result.success is False
    assert result.is_draft is True
    assert result.submittable is False
    assert "1 UNVERIFIABLE" in result.blocked_reason
    assert "_DRAFT" in Path(result.final_path).name


def test_judgment_rule_without_evidence_is_review_required_and_blocks_final(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    _write_registry(registry, [_lesson("L-JUDGE", "judgment")])

    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        guards={},
        save_report=False,
    )

    entry = report.rules[0]
    assert entry["id"] == "L-JUDGE"
    assert entry["status"] == "REVIEW_REQUIRED"
    assert entry["evidence"] == ""
    assert entry["reason"] == "judgment rule requires human evidence"
    assert report.summary["review_required"] == 1
    assert report.can_finalize is False

    result = finalize_artifact(artifact, report)
    assert result.success is False
    assert result.is_draft is True
    assert result.submittable is False
    assert "1 REVIEW_REQUIRED" in result.blocked_reason
    assert "_DRAFT" in Path(result.final_path).name


def test_declared_rule_missing_from_registry_blocks_final(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    _write_registry(registry, [_lesson("L-PRESENT", "mechanized")], total=2)

    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        guards=_passing_guard("L-PRESENT"),
        save_report=False,
    )

    assert report.summary["missing"] == 1
    assert report.summary["duplicate"] == 0
    assert report.summary["fail"] == 0
    assert report.summary["review_required"] == 0
    assert report.summary["unverifiable"] == 0
    assert report.can_finalize is False

    result = finalize_artifact(artifact, report)
    assert result.success is False
    assert result.is_draft is True
    assert result.submittable is False
    assert "missing=1" in result.blocked_reason
    assert "_DRAFT" in Path(result.final_path).name


def test_duplicate_rule_id_blocks_final(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    lesson = _lesson("L-DUP", "mechanized")
    _write_registry(registry, [lesson, dict(lesson)])

    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        guards=_passing_guard("L-DUP"),
        save_report=False,
    )

    assert report.summary["duplicate"] == 1
    assert report.summary["missing"] == 0
    assert report.summary["fail"] == 0
    assert report.summary["review_required"] == 0
    assert report.summary["unverifiable"] == 0
    assert report.can_finalize is False

    result = finalize_artifact(artifact, report)
    assert result.success is False
    assert result.is_draft is True
    assert result.submittable is False
    assert "duplicate=1" in result.blocked_reason
    assert "_DRAFT" in Path(result.final_path).name


def test_report_save_failure_blocks_final(tmp_path: Path, monkeypatch) -> None:
    artifact = _artifact(tmp_path)
    registry = tmp_path / "lessons_coverage.json"
    _write_registry(registry, [_lesson("L-SAVE", "mechanized")])
    report_path = tmp_path / "lrule_report.json"

    def fail_save(self, path):
        raise OSError("read-only report destination")

    monkeypatch.setattr("auto_write.services.lrule_enforcer.LRuleReport.save", fail_save)
    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        guards=_passing_guard("L-SAVE"),
        report_path=report_path,
    )

    assert report_path.exists() is False
    assert report.can_finalize is False
    assert "lrule report save failed" in report.finalization_blocked_reason
    assert report.summary["fail"] == 0
    assert report.summary["review_required"] == 0
    assert report.summary["unverifiable"] == 0

    result = finalize_artifact(artifact, report)
    assert result.success is False
    assert result.is_draft is True
    assert result.submittable is False
    assert "lrule report save failed" in result.blocked_reason
    assert "_DRAFT" in Path(result.final_path).name


def test_caller_supplied_final_path_is_not_materialized_when_report_blocks(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path, "work.docx")
    registry = tmp_path / "lessons_coverage.json"
    _write_registry(registry, [_lesson("L-MECH", "mechanized")])
    report = enforce_lrules(
        Domain.BUSINESS_PLAN,
        artifact_path=artifact,
        lessons_path=registry,
        guards={},
        save_report=False,
    )
    assert report.can_finalize is False

    requested_final = tmp_path / "submission.docx"
    result = finalize_artifact(
        artifact,
        report,
        output_path=requested_final,
        materialize=True,
    )

    assert result.success is False
    assert result.is_draft is True
    assert result.submittable is False
    assert Path(result.final_path).name == "submission_DRAFT.docx"
    assert Path(result.final_path).exists()
    assert requested_final.exists() is False
    assert Path(result.final_path).read_bytes() == artifact.read_bytes()
