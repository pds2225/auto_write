# -*- coding: utf-8 -*-
"""Runner contract: missing external data is PARTIAL, and manifests are read-only."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import assess_fields, find_t02_auto_targets
from core.docx.services.hwpx_safety_report import (
    build_report,
    decide_overall,
    run_dry_run_result,
    run_holdout_manifest,
)

_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HS = "http://www.hancom.co.kr/hwpml/2011/section"


def _stage(status: str, **kwargs) -> dict:
    payload = {"status": status, "failures": [], "test_count": 1, "case_count": 0, "unsafe_auto_count": 0, "out_of_scope_xml_change": 0}
    payload.update(kwargs)
    return payload


def _hwpx(path: Path) -> str:
    section = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<hs:sec xmlns:hp="{_HP}" xmlns:hs="{_HS}">'
        "<hp:p><hp:run><hp:tbl><hp:tr>"
        '<hp:tc><hp:subList><hp:p><hp:run><hp:t>기업명</hp:t></hp:run></hp:p></hp:subList>'
        '<hp:cellAddr rowAddr="0" colAddr="0"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
        '<hp:tc><hp:subList><hp:p><hp:run></hp:run></hp:p></hp:subList>'
        '<hp:cellAddr rowAddr="0" colAddr="1"/><hp:cellSpan rowSpan="1" colSpan="1"/></hp:tc>'
        "</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>"
    )
    hpf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<opf:package xmlns:opf="http://www.idpf.org/2007/opf">'
        '<opf:manifest><opf:item id="s0" href="Contents/section0.xml" media-type="application/xml"/></opf:manifest>'
        '<opf:spine><opf:itemref idref="s0"/></opf:spine></opf:package>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Contents/section0.xml", section.encode("utf-8"))
        archive.writestr("Contents/content.hpf", hpf.encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_external_results_stay_partial() -> None:
    report = build_report(
        unit=_stage("PASS"),
        golden=_stage("PASS"),
        xml_diff=_stage("PASS"),
        holdout=_stage("NOT_AVAILABLE"),
        dry_run=_stage("NOT_AVAILABLE"),
        sha_changes=[],
    )
    assert report["totals"]["OVERALL"] == "PARTIAL"
    assert report["totals"]["UNSAFE_AUTO_COUNT"] == 0
    assert report["totals"]["HOLDOUT"] == "NOT_AVAILABLE"
    assert report["totals"]["DRY_RUN_367"] == "NOT_AVAILABLE"


def test_local_failure_is_not_hidden_by_missing_external_data() -> None:
    assert decide_overall("FAIL", "PASS", "PASS", "NOT_AVAILABLE", "NOT_AVAILABLE", unsafe_auto=0, out_of_scope=0, blockers=0) == "FAIL"
    assert decide_overall("PASS", "PASS", "PASS", "NOT_AVAILABLE", "NOT_AVAILABLE", unsafe_auto=1, out_of_scope=0, blockers=0) == "FAIL"
    assert decide_overall("PASS", "PASS", "PASS", "PASS", "PASS", unsafe_auto=0, out_of_scope=0, blockers=0) == "PASS"


def test_holdout_manifest_is_not_overwritten_and_empty_is_not_pass(tmp_path: Path) -> None:
    manifest = tmp_path / "holdout_manifest.json"
    manifest.write_text(json.dumps({"schema": "hwpx-safety-holdout-v1", "cases": []}), encoding="utf-8")
    before = manifest.read_bytes()
    result = run_holdout_manifest(manifest, tmp_path)
    assert manifest.read_bytes() == before
    assert result["status"] == "NOT_AVAILABLE"
    assert result["reason"] == "SKIPPED_WITH_REASON"
    missing = run_holdout_manifest(tmp_path / "absent.json", tmp_path)
    assert missing["status"] == "NOT_AVAILABLE"


def test_holdout_manifest_runs_never_auto_without_baked_answers(tmp_path: Path) -> None:
    form = tmp_path / "form.hwpx"
    sha = _hwpx(form)
    index = index_hwpx_structure(form)
    targets = find_t02_auto_targets(index)
    assert len(targets) == 1
    records = assess_fields(index)
    value_record = next(item for item in records if item.paragraph_index == targets[0].paragraph_index and item.field_type == "T02")
    assert value_record.eligible is True
    assert value_record.auto_write_allowed is False
    assert value_record.decision != "AUTO"
    assert value_record.write_target is None
    label = next(item for item in index.sections[0].paragraphs if item.raw_text == "기업명")
    manifest = tmp_path / "holdout_manifest.json"
    manifest.write_text(json.dumps({
        "schema": "hwpx-safety-holdout-v1",
        "cases": [{
            "file": str(form),
            "sha256": sha,
            "never_auto": [{
                "section_index": targets[0].section_index,
                "paragraph_index": targets[0].paragraph_index,
                "run_index": targets[0].run_index,
                "text": "",
            }],
            "forbid_labels": ["(서술 칸)", "해당"],
        }],
    }), encoding="utf-8")
    before = manifest.read_bytes()
    result = run_holdout_manifest(manifest, tmp_path)
    assert manifest.read_bytes() == before
    assert result["status"] == "PASS"
    assert result["failures"] == []
    label_manifest = {
        "schema": "hwpx-safety-holdout-v1",
        "cases": [{
            "file": str(form),
            "sha256": sha,
            "never_auto": [{"section_index": 0, "paragraph_index": label.paragraph_index, "run_index": 0, "text": "기업명"}],
        }],
    }
    manifest.write_text(json.dumps(label_manifest), encoding="utf-8")
    passed = run_holdout_manifest(manifest, tmp_path)
    assert passed["status"] == "PASS"


def test_dry_run_result_is_included_without_rewriting_rules(tmp_path: Path) -> None:
    result_path = tmp_path / "dry_run_result.json"
    result_path.write_text(json.dumps({
        "schema": "hwpx-safety-dry-run-v1",
        "files_checked": 367,
        "unsafe_auto_count": 2,
        "out_of_scope_xml_change": 1,
        "failures": [],
    }), encoding="utf-8")
    before = result_path.read_bytes()
    result = run_dry_run_result(result_path, tmp_path)
    assert result_path.read_bytes() == before
    assert result["status"] == "FAIL"
    assert result["unsafe_auto_count"] == 2
    assert result["out_of_scope_xml_change"] == 1
    absent = run_dry_run_result(tmp_path / "missing.json", tmp_path)
    assert absent["status"] == "NOT_AVAILABLE"
    assert absent["reason"] == "SKIPPED_WITH_REASON"
