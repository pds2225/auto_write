# -*- coding: utf-8 -*-
"""Assemble the one-command HWPX safety report.

External Holdout and Dry-run files are read only. This module never writes
those paths and does not invent their cases.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import assess_fields
from core.docx.services.hwpx_safety_golden import (
    _LOCKED_CHOICE_LABELS,
    _LOCKED_FAKE_LABELS,
    _compact,
    _run_text,
    _load_roots,
)
from core.docx.services.hwpx_xml_scope_diff import sha256_file

HOLDOUT_SCHEMA = "hwpx-safety-holdout-v1"
DRY_RUN_SCHEMA = "hwpx-safety-dry-run-v1"
_FAILURE_KEYS = (
    "file", "stage", "field", "structure_type", "decision", "expected", "actual",
    "reason_code", "xml_location", "before", "after", "severity",
)


def blank_failure(**kwargs) -> dict:
    payload = {key: "" for key in _FAILURE_KEYS}
    payload["severity"] = "REVIEW_REQUIRED"
    payload.update(kwargs)
    return payload


def decide_overall(unit: str, golden: str, xml_diff: str, holdout: str, dry_run: str, *, unsafe_auto: int, out_of_scope: int, blockers: int) -> str:
    """PASS only when every stage actually ran and the safety counts are zero."""
    local_failed = any(status == "FAIL" for status in (unit, golden, xml_diff, holdout, dry_run))
    if local_failed or unsafe_auto or out_of_scope or blockers:
        return "FAIL"
    if holdout == "PASS" and dry_run == "PASS":
        return "PASS"
    return "PARTIAL"


def _not_available(detail: str) -> dict:
    return {
        "status": "NOT_AVAILABLE",
        "reason": "SKIPPED_WITH_REASON",
        "detail": detail,
        "failures": [],
        "case_count": 0,
    }


def _schema_failure(stage: str, path: Path, detail: str) -> dict:
    return {
        "status": "FAIL",
        "reason": "SCHEMA_INVALID",
        "detail": detail,
        "failures": [blank_failure(
            file=str(path), stage=stage, field="schema", structure_type="",
            decision="", expected=HOLDOUT_SCHEMA if stage == "holdout" else DRY_RUN_SCHEMA,
            actual=detail, reason_code="SCHEMA_INVALID", severity="BLOCKER",
        )],
        "case_count": 0,
    }


def _read_json(path: Path) -> tuple[dict | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except json.JSONDecodeError as exc:
        return None, str(exc)


def run_holdout_manifest(path: Path, data_dir: Path) -> dict:
    """Execute a dropped-in Holdout manifest. Missing file is NOT_AVAILABLE."""
    if not path.is_file():
        return _not_available("Holdout manifest가 없습니다.")
    before = path.read_bytes()
    payload, error = _read_json(path)
    if path.read_bytes() != before:
        return _schema_failure("holdout", path, "manifest가 읽는 동안 바뀌었습니다.")
    if payload is None:
        return _schema_failure("holdout", path, error)
    if payload.get("schema") != HOLDOUT_SCHEMA:
        return _schema_failure("holdout", path, f"schema={payload.get('schema')!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return _not_available("Holdout cases가 비어 있습니다.")
    failures: list[dict] = []
    for case in cases:
        failures.extend(_holdout_case(case, data_dir))
    return {
        "status": "FAIL" if failures else "PASS",
        "reason": "CHECKED" if not failures else "HOLDOUT_FAILED",
        "detail": f"cases={len(cases)}",
        "failures": failures,
        "case_count": len(cases),
    }


def _resolve_case_file(raw: str, data_dir: Path) -> Path:
    candidate = Path(raw)
    if candidate.is_file():
        return candidate
    nested = data_dir / raw
    if nested.is_file():
        return nested
    return candidate


def _holdout_case(case: dict, data_dir: Path) -> list[dict]:
    name = str(case.get("file") or "")
    path = _resolve_case_file(name, data_dir)
    stage = "holdout"
    if not path.is_file():
        return [blank_failure(
            file=name, stage=stage, field=name, reason_code="FILE_MISSING",
            expected="present", actual="absent", severity="BLOCKER",
        )]
    before_bytes = path.read_bytes()
    actual_sha = sha256_file(path)
    expected_sha = str(case.get("sha256") or "").lower()
    if not expected_sha or actual_sha != expected_sha:
        return [blank_failure(
            file=str(path), stage=stage, field="sha256", reason_code="SHA_MISMATCH",
            expected=expected_sha, actual=actual_sha, before=expected_sha, after=actual_sha,
            severity="BLOCKER",
        )]
    index = index_hwpx_structure(path)
    if path.read_bytes() != before_bytes:
        return [blank_failure(file=str(path), stage=stage, reason_code="SOURCE_MUTATED", severity="BLOCKER")]
    assessments = assess_fields(index)
    roots = _load_roots(path, {section.section_member for section in index.sections})
    failures: list[dict] = []
    for anchor in case.get("never_auto") or []:
        section_index = int(anchor.get("section_index", 0))
        paragraph_index = int(anchor.get("paragraph_index", -1))
        run_index = anchor.get("run_index")
        member = index.sections[section_index].section_member if section_index < len(index.sections) else ""
        location = f"{member}#s[{section_index}]/p[{paragraph_index}]"
        if run_index is not None and member:
            actual_text = _run_text(roots, member, paragraph_index, int(run_index))
            expected_text = anchor.get("text")
            if expected_text is not None and actual_text != expected_text:
                failures.append(blank_failure(
                    file=str(path), stage=stage, field=str(anchor.get("id") or location),
                    structure_type="HOLDOUT", decision="", expected=str(expected_text), actual=actual_text,
                    reason_code="TEXT_MISMATCH", xml_location=location, before=str(expected_text),
                    after=actual_text, severity="BLOCKER",
                ))
        authorized = next((
            item for item in assessments
            if (item.decision == "AUTO" or item.auto_write_allowed)
            and item.section_index == section_index
            and item.paragraph_index == paragraph_index
        ), None)
        if authorized is not None:
            failures.append(blank_failure(
                file=str(path), stage=stage, field=str(anchor.get("id") or location),
                structure_type=authorized.field_type, decision=authorized.decision, expected="NOT_AUTHORIZED",
                actual=authorized.field_label or "AUTO",
                reason_code="UNSAFE_AUTO", xml_location=location, severity="BLOCKER",
            ))
    forbidden = {_compact(str(label)) for label in (case.get("forbid_labels") or [])}
    forbidden.update(_LOCKED_FAKE_LABELS)
    forbidden.update(_LOCKED_CHOICE_LABELS)
    for item in assessments:
        label = item.field_label or ""
        if label and (_compact(label) in forbidden or label in forbidden) and (item.decision == "AUTO" or item.auto_write_allowed):
            failures.append(blank_failure(
                file=str(path), stage=stage, field=label, structure_type=item.field_type,
                decision=item.decision, expected="NOT_AUTO", actual=label,
                reason_code="FAKE_LABEL" if label in _LOCKED_FAKE_LABELS else "UNSAFE_AUTO",
                severity="BLOCKER",
            ))
    return failures


def run_dry_run_result(path: Path, data_dir: Path) -> dict:
    """Include a dropped-in Dry-run result. This does not re-judge the 367 files."""
    if not path.is_file():
        return _not_available("Dry-run 결과 파일이 없습니다.")
    before = path.read_bytes()
    payload, error = _read_json(path)
    if path.read_bytes() != before:
        return _schema_failure("dry_run", path, "결과 파일이 읽는 동안 바뀌었습니다.")
    if payload is None:
        failed = _schema_failure("dry_run", path, error)
        failed["failures"][0]["expected"] = DRY_RUN_SCHEMA
        return failed
    if payload.get("schema") != DRY_RUN_SCHEMA:
        failed = _schema_failure("dry_run", path, f"schema={payload.get('schema')!r}")
        failed["failures"][0]["expected"] = DRY_RUN_SCHEMA
        return failed
    required = ("files_checked", "unsafe_auto_count", "out_of_scope_xml_change", "failures")
    if any(key not in payload for key in required):
        return _schema_failure("dry_run", path, "필수 키가 없습니다.")
    files_checked = int(payload.get("files_checked") or 0)
    if files_checked <= 0:
        return _not_available("Dry-run files_checked가 0입니다.")
    failures = [_normalize_failure(item, "dry_run") for item in payload.get("failures") or []]
    unsafe = int(payload.get("unsafe_auto_count") or 0)
    out_of_scope = int(payload.get("out_of_scope_xml_change") or 0)
    if unsafe and not any(item["reason_code"] == "UNSAFE_AUTO" for item in failures):
        failures.append(blank_failure(
            file=str(path), stage="dry_run", field="unsafe_auto_count", structure_type="T02",
            decision="AUTO", expected="0", actual=str(unsafe), reason_code="UNSAFE_AUTO",
            severity="BLOCKER",
        ))
    if out_of_scope and not any(item["reason_code"] == "OUT_OF_SCOPE_XML_CHANGE" for item in failures):
        failures.append(blank_failure(
            file=str(path), stage="dry_run", field="out_of_scope_xml_change",
            decision="FAIL", expected="0", actual=str(out_of_scope),
            reason_code="OUT_OF_SCOPE_XML_CHANGE", severity="BLOCKER",
        ))
    for entry in payload.get("files") or []:
        raw = str(entry.get("file") or "")
        expected = str(entry.get("sha256") or "").lower()
        if not raw or not expected:
            continue
        file_path = _resolve_case_file(raw, data_dir)
        if not file_path.is_file():
            failures.append(blank_failure(
                file=raw, stage="dry_run", field="sha256", reason_code="FILE_MISSING",
                expected=expected, actual="absent", severity="BLOCKER",
            ))
            continue
        actual = sha256_file(file_path)
        if actual != expected:
            failures.append(blank_failure(
                file=str(file_path), stage="dry_run", field="sha256", reason_code="SHA_MISMATCH",
                expected=expected, actual=actual, before=expected, after=actual, severity="BLOCKER",
            ))
    blockers = any(item["severity"] == "BLOCKER" for item in failures)
    status = "FAIL" if blockers or unsafe or out_of_scope else "PASS"
    return {
        "status": status,
        "reason": "INCLUDED" if status == "PASS" else "DRY_RUN_FAILED",
        "detail": f"files_checked={files_checked}",
        "failures": failures,
        "case_count": files_checked,
        "unsafe_auto_count": unsafe,
        "out_of_scope_xml_change": out_of_scope,
    }


def _normalize_failure(item: dict, stage: str) -> dict:
    payload = blank_failure(stage=stage)
    if isinstance(item, dict):
        for key in _FAILURE_KEYS:
            if key in item and item[key] is not None:
                payload[key] = item[key]
    payload["stage"] = payload["stage"] or stage
    if payload["severity"] not in {"BLOCKER", "HIGH_RISK", "REGRESSION", "REVIEW_REQUIRED"}:
        payload["severity"] = "REVIEW_REQUIRED"
    return payload


def render_markdown(report: dict) -> str:
    totals = report["totals"]
    lines = [
        "# HWPX 안전검증 요약",
        "",
        f"TOTAL_TESTS = {totals['TOTAL_TESTS']}",
        f"UNIT_TESTS = {totals['UNIT_TESTS']}",
        f"GOLDEN_10 = {totals['GOLDEN_10']}",
        f"XML_DIFF = {totals['XML_DIFF']}",
        f"HOLDOUT = {totals['HOLDOUT']}",
        f"DRY_RUN_367 = {totals['DRY_RUN_367']}",
        f"UNSAFE_AUTO_COUNT = {totals['UNSAFE_AUTO_COUNT']}",
        f"OUT_OF_SCOPE_XML_CHANGE = {totals['OUT_OF_SCOPE_XML_CHANGE']}",
        f"REGRESSION_COUNT = {totals['REGRESSION_COUNT']}",
        f"BLOCKERS = {totals['BLOCKERS']}",
        f"OVERALL = {totals['OVERALL']}",
        "",
        report.get("external_note", ""),
        "",
    ]
    grouped = {name: [] for name in ("BLOCKER", "HIGH_RISK", "REGRESSION", "REVIEW_REQUIRED")}
    for failure in report.get("failures") or []:
        grouped.setdefault(failure.get("severity") or "REVIEW_REQUIRED", []).append(failure)
    for name in ("BLOCKER", "HIGH_RISK", "REGRESSION", "REVIEW_REQUIRED"):
        lines.append(f"## {name}")
        items = grouped.get(name) or []
        if not items:
            lines.append("없음")
            lines.append("")
            continue
        for item in items:
            lines.append(
                f"- {item.get('file', '')} / {item.get('stage', '')} / {item.get('field', '')} / "
                f"{item.get('reason_code', '')}: expected {item.get('expected', '')} / actual {item.get('actual', '')}"
            )
        lines.append("")
    summary = report.get("golden_summary") or ""
    if summary:
        lines.append("## GOLDEN 파일")
        lines.append(summary.rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_report(*, unit: dict, golden: dict, xml_diff: dict, holdout: dict, dry_run: dict, sha_changes: list[dict]) -> dict:
    failures: list[dict] = []
    failures.extend(unit.get("failures") or [])
    failures.extend(golden.get("failures") or [])
    failures.extend(xml_diff.get("failures") or [])
    failures.extend(holdout.get("failures") or [])
    failures.extend(dry_run.get("failures") or [])
    failures.extend(sha_changes)
    unsafe = int(golden.get("unsafe_auto_count") or 0) + int(dry_run.get("unsafe_auto_count") or 0)
    unsafe += sum(1 for item in failures if item.get("reason_code") == "UNSAFE_AUTO" and item.get("stage") == "holdout")
    out_of_scope = int(xml_diff.get("out_of_scope_xml_change") or 0) + int(dry_run.get("out_of_scope_xml_change") or 0)
    blockers = [item for item in failures if item.get("severity") == "BLOCKER"]
    regressions = [item for item in failures if item.get("severity") == "REGRESSION"]
    overall = decide_overall(
        unit["status"], golden["status"], xml_diff["status"], holdout["status"], dry_run["status"],
        unsafe_auto=unsafe, out_of_scope=out_of_scope, blockers=len(blockers),
    )
    total_tests = (
        int(unit.get("test_count") or 0)
        + int(golden.get("test_count") or 0)
        + int(xml_diff.get("test_count") or 0)
        + int(holdout.get("case_count") or 0)
        + (int(dry_run.get("case_count") or 0) if dry_run.get("status") == "PASS" or dry_run.get("reason") == "DRY_RUN_FAILED" else 0)
    )
    if holdout["status"] == "NOT_AVAILABLE" or dry_run["status"] == "NOT_AVAILABLE":
        note = "Holdout 또는 Dry-run 자료가 아직 없습니다. 실행된 검증이 통과해도 OVERALL은 PASS가 아니라 PARTIAL입니다."
    else:
        note = "Holdout과 Dry-run 자료를 읽어 요약에 포함했습니다."
    totals = {
        "TOTAL_TESTS": total_tests,
        "UNIT_TESTS": unit["status"],
        "GOLDEN_10": golden["status"],
        "XML_DIFF": xml_diff["status"],
        "HOLDOUT": holdout["status"] if holdout["status"] != "NOT_AVAILABLE" else "NOT_AVAILABLE",
        "DRY_RUN_367": dry_run["status"] if dry_run["status"] != "NOT_AVAILABLE" else "NOT_AVAILABLE",
        "UNSAFE_AUTO_COUNT": unsafe,
        "OUT_OF_SCOPE_XML_CHANGE": out_of_scope,
        "REGRESSION_COUNT": len(regressions),
        "BLOCKERS": len(blockers),
        "OVERALL": overall,
    }
    return {
        "totals": totals,
        "external_note": note,
        "stages": {
            "unit": unit,
            "golden": golden,
            "xml_diff": xml_diff,
            "holdout": {key: value for key, value in holdout.items() if key != "failures"},
            "dry_run": {key: value for key, value in dry_run.items() if key != "failures"},
        },
        "failures": failures,
        "sha_changes": sha_changes,
    }
