# -*- coding: utf-8 -*-
"""One-command HWPX safety validation.

    python app/tools/hwpx_safety_validate.py

Reads, and never writes, optional external results:

    data/hwpx_safety/external/holdout_manifest.json
    data/hwpx_safety/external/dry_run_result.json

Holdout schema ``hwpx-safety-holdout-v1`` has ``cases`` with ``file``,
``sha256``, optional ``never_auto`` and ``forbid_labels``. Dry-run schema
``hwpx-safety-dry-run-v1`` has ``files_checked``, ``unsafe_auto_count``,
``out_of_scope_xml_change``, and ``failures``. Missing files stay
NOT_AVAILABLE and the overall result stays PARTIAL.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.docx.services.hwpx_safety_golden import GOLDEN_CASES, evaluate_golden10, format_golden_report
from core.docx.services.hwpx_safety_report import (
    blank_failure,
    build_report,
    render_markdown,
    run_dry_run_result,
    run_holdout_manifest,
)
from core.docx.services.hwpx_xml_scope_diff import sha256_file

REPO = Path(__file__).resolve().parents[2]
UNIT_FILES = [
    "app/tests/test_hwpx_structure_index.py",
    "app/tests/test_hwpx_protected_regions.py",
    "app/tests/test_hwpx_exact_write.py",
    "app/tests/test_hwpx_t02_auto.py",
    "app/tests/test_hwpx_merged_value.py",
    "app/tests/test_hwpx_nested_leaf.py",
    "app/tests/test_hwpx_repeated_row.py",
    "app/tests/test_hwpx_guidance_narrative.py",
    "app/tests/test_hwpx_inline_field.py",
    "app/tests/test_hwpx_safety_runner.py",
]
GOLDEN_FILES = ["app/tests/test_hwpx_safety_golden10.py"]
XML_FILES = ["app/tests/test_hwpx_xml_scope_diff.py"]


def _hashes(data_dir: Path) -> dict[str, str]:
    found = {}
    for case in GOLDEN_CASES:
        path = data_dir / case["file"]
        if path.is_file():
            found[case["file"]] = sha256_file(path)
    return found


def _sha_changes(before: dict[str, str], after: dict[str, str]) -> list[dict]:
    failures = []
    names = sorted(set(before) | set(after))
    for name in names:
        if before.get(name) == after.get(name) and name in before and name in after:
            continue
        failures.append(blank_failure(
            file=name, stage="sha", field="source_sha256", structure_type="SOURCE",
            decision="", expected=before.get(name, ""), actual=after.get(name, ""),
            reason_code="SHA_CHANGED", xml_location=name,
            before=before.get(name, ""), after=after.get(name, ""), severity="BLOCKER",
        ))
    return failures


def _pytest(files: list[str], basetemp: Path) -> dict:
    basetemp.mkdir(parents=True, exist_ok=True)
    junit = basetemp / "junit.xml"
    if junit.exists():
        junit.unlink()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["TMP"] = str(basetemp)
    env["TEMP"] = str(basetemp)
    command = [
        sys.executable, "-m", "pytest", *files, "-q", "--tb=line",
        f"--junitxml={junit}", f"--basetemp={basetemp / 'cases'}",
    ]
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    parsed = _parse_junit(junit)
    status = "PASS" if completed.returncode == 0 and parsed["failed"] == 0 else "FAIL"
    return {
        "status": status,
        "test_count": parsed["test_count"],
        "passed": parsed["passed"],
        "failed": parsed["failed"],
        "failures": parsed["failures"],
        "returncode": completed.returncode,
        "output": (completed.stdout or "") + (completed.stderr or ""),
    }


def _parse_junit(path: Path) -> dict:
    if not path.is_file():
        return {"test_count": 0, "passed": 0, "failed": 0, "failures": [blank_failure(
            stage="pytest", field="junit", reason_code="PYTEST_FAILURE",
            expected="junit", actual="missing", severity="BLOCKER",
        )]}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    test_count = 0
    failed = 0
    failures = []
    for suite in suites:
        test_count += int(suite.attrib.get("tests") or 0)
        failed += int(suite.attrib.get("failures") or 0) + int(suite.attrib.get("errors") or 0)
        for case in suite.findall("testcase"):
            problem = case.find("failure")
            if problem is None:
                problem = case.find("error")
            if problem is None:
                continue
            failures.append(blank_failure(
                file=case.attrib.get("file") or case.attrib.get("classname") or "",
                stage="pytest",
                field=case.attrib.get("name") or "",
                structure_type="",
                decision="FAIL",
                expected="PASS",
                actual=(problem.attrib.get("message") or problem.text or "")[:500],
                reason_code="PYTEST_FAILURE",
                xml_location=case.attrib.get("classname") or "",
                severity="REGRESSION",
            ))
    return {
        "test_count": test_count,
        "passed": test_count - failed,
        "failed": failed,
        "failures": failures,
    }


def _live_external(data_dir: Path, external_dir: Path) -> tuple[dict, dict]:
    """Re-run Holdout and Dry-run from the saved file lists. Do not trust old verdicts."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hwpx_safety_recheck", Path(__file__).with_name("hwpx_safety_recheck.py"),
    )
    recheck = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recheck)
    holdout_path = data_dir / "holdout_validation_results.json"
    dry_path = data_dir / "dry_run_367_summary.json"
    if holdout_path.is_file():
        payload = json.loads(holdout_path.read_text(encoding="utf-8"))
        before = holdout_path.read_bytes()
        result = recheck._holdout(payload["FILES"])
        if holdout_path.read_bytes() != before:
            raise RuntimeError("holdout 원본 보고서가 변경되었습니다.")
        failures = [
            blank_failure(
                file=item["file"], stage="holdout", field=hit.get("label", ""),
                structure_type="T02", decision="AUTO", expected="NOT_AUTO",
                actual=hit.get("reason", ""), reason_code=hit.get("reason", "UNSAFE_AUTO"),
                severity="HIGH_RISK" if hit.get("reason") != "SOURCE_MUTATED" else "BLOCKER",
            )
            for item in result["failures"]
            for hit in item.get("unsafe", [{"reason": item.get("reason", "")}])
        ]
        holdout = {
            "status": "PASS" if result["unsafe_auto_count"] == 0 and result["high_risk"] == 0 else "FAIL",
            "reason": "RECHECKED",
            "detail": f"files={result['files']} unsafe={result['unsafe_auto_count']} high_risk={result['high_risk']}",
            "failures": failures,
            "case_count": result["files"],
        }
    else:
        holdout = run_holdout_manifest(external_dir / "holdout_manifest.json", data_dir)
    if dry_path.is_file():
        payload = json.loads(dry_path.read_text(encoding="utf-8"))
        before = dry_path.read_bytes()
        result = recheck._dry_run(payload["documents"])
        if dry_path.read_bytes() != before:
            raise RuntimeError("dry-run 원본 보고서가 변경되었습니다.")
        failures = [
            blank_failure(
                file=item.get("file", ""), stage="dry_run", field=item.get("label", ""),
                structure_type="T02", decision="AUTO", expected="0", actual=item.get("reason", ""),
                reason_code=item.get("reason", "UNSAFE_AUTO"), severity="BLOCKER",
            )
            for item in result["examples"]
        ]
        dry_run = {
            "status": "PASS" if result["sign_consent_auto"] == 0 and result["duplicate_target_link"] == 0 and not result["sha_changed"] else "FAIL",
            "reason": "RECHECKED",
            "detail": f"files_checked={result['files']} auto={result['auto']}",
            "failures": failures,
            "case_count": result["files"],
            "unsafe_auto_count": result["sign_consent_auto"],
            "out_of_scope_xml_change": 0,
        }
    else:
        dry_run = run_dry_run_result(external_dir / "dry_run_result.json", data_dir)
    return holdout, dry_run


def run_validation(data_dir: Path, external_dir: Path, output_dir: Path) -> dict:
    """Run unit, golden, and XML diff, then attach external results if present."""
    output_dir.mkdir(parents=True, exist_ok=True)
    basetemp = output_dir / "pytest-basetemp"
    before = _hashes(data_dir)
    unit = _pytest(UNIT_FILES, basetemp / "unit")
    for item in unit["failures"]:
        item["stage"] = "unit"
    golden_eval = evaluate_golden10(data_dir)
    golden_pytest = _pytest(GOLDEN_FILES, basetemp / "golden")
    golden_failures = list(golden_eval["failures"])
    golden_failures.extend(golden_pytest["failures"])
    if golden_eval["ok"] != (golden_pytest["status"] == "PASS"):
        golden_failures.append(blank_failure(
            file="golden10", stage="golden10", field="harness",
            reason_code="HARNESS_MISMATCH", expected=str(golden_eval["ok"]),
            actual=golden_pytest["status"], severity="BLOCKER",
        ))
    golden = {
        "status": "PASS" if golden_eval["ok"] and golden_pytest["status"] == "PASS" else "FAIL",
        "test_count": golden_pytest["test_count"] or golden_eval["file_count"],
        "failures": golden_failures,
        "unsafe_auto_count": golden_eval["unsafe_auto_count"],
        "summary": format_golden_report(golden_eval),
        "files": golden_eval["files"],
    }
    xml_diff = _pytest(XML_FILES, basetemp / "xml")
    xml_diff["out_of_scope_xml_change"] = 0 if xml_diff["status"] == "PASS" else xml_diff["failed"]
    for item in xml_diff["failures"]:
        item["stage"] = "xml_diff"
    holdout, dry_run = _live_external(data_dir, external_dir)
    after = _hashes(data_dir)
    report = build_report(
        unit=unit,
        golden=golden,
        xml_diff=xml_diff,
        holdout=holdout,
        dry_run=dry_run,
        sha_changes=_sha_changes(before, after),
    )
    report["golden_summary"] = golden["summary"]
    report["original_sha256"] = before
    json_path = output_dir / "validation_report.json"
    md_path = output_dir / "validation_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["md_path"] = str(md_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="HWPX 안전검증을 한 번에 실행합니다.")
    parser.add_argument("--data-dir", default=str(REPO / "data"))
    parser.add_argument("--external-dir", default=str(REPO / "data" / "hwpx_safety" / "external"))
    parser.add_argument("--output-dir", default=str(REPO / "data" / "hwpx_safety" / "cursor"))
    args = parser.parse_args()
    report = run_validation(Path(args.data_dir), Path(args.external_dir), Path(args.output_dir))
    totals = report["totals"]
    print(render_markdown(report))
    print(f"JSON {report['json_path']}")
    print(f"MD {report['md_path']}")
    return 0 if totals["OVERALL"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
