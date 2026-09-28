# -*- coding: utf-8 -*-
"""Re-check Holdout 27 and the 367-form dry-run after rule changes.

Reads the existing file lists only. Does not overwrite those reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.docx.services.hwpx_analysis_adapter import index_hwpx_structure
from core.docx.services.hwpx_protected_regions import (
    _UNIT_LABELS,
    _sign_consent_label,
    assess_fields,
    find_t02_auto_targets,
)
from core.docx.services.hwpx_xml_scope_diff import sha256_file
import re

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "hwpx_safety" / "cursor"
_DATE_ATOM = re.compile(r"^(?:\d{2,4}년|\d{1,2}월|\d{1,2}일|참고[\d.．:：]*|서식\d+)$")


def _unsafe_label(label: str) -> str:
    compact = re.sub(r"\s+", "", label or "")
    if not compact:
        return "EMPTY_LABEL"
    if compact in _UNIT_LABELS or _DATE_ATOM.fullmatch(compact):
        return "UNIT_OR_DATE_OR_MARKER"
    if _sign_consent_label(compact):
        return "SIGN_CONSENT"
    if any(mark in label for mark in ("○", "◯", "◦", "●", "□", "■", "☐", "✓", "✔")):
        return "CHOICE_MARK"
    return ""


def _load_form_rows(summary: dict) -> list[dict]:
    documents = summary.get("documents")
    if isinstance(documents, list) and len(documents) >= 367:
        return documents
    raise SystemExit("367개 파일 목록을 찾지 못했습니다.")


def _holdout(files: list[dict]) -> dict:
    failures = []
    unsafe = 0
    high = 0
    for item in files:
        path = DATA / item["FILE"]
        before = sha256_file(path) if path.is_file() else ""
        if not path.is_file():
            failures.append({"file": item["FILE"], "reason": "FILE_MISSING", "severity": "BLOCKER"})
            high += 1
            continue
        index = index_hwpx_structure(path)
        targets = find_t02_auto_targets(index)
        keys: dict[tuple, int] = {}
        file_unsafe = []
        for target in targets:
            key = (target.section_index, target.table_index, target.row, target.col)
            keys[key] = keys.get(key, 0) + 1
            reason = _unsafe_label(target.field_label)
            if reason:
                file_unsafe.append({"label": target.field_label, "reason": reason, "row": target.row, "col": target.col})
        duplicates = [key for key, count in keys.items() if count > 1]
        for key in duplicates:
            file_unsafe.append({"label": "", "reason": "DUPLICATE_TARGET", "row": key[2], "col": key[3]})
        if sha256_file(path) != before:
            file_unsafe.append({"label": "", "reason": "SOURCE_MUTATED"})
        if file_unsafe:
            high += 1
            unsafe += len(file_unsafe)
            failures.append({"file": item["FILE"], "unsafe": file_unsafe, "severity": "HIGH_RISK"})
    return {
        "files": len(files),
        "fail": len(failures),
        "high_risk": high,
        "unsafe_auto_count": unsafe,
        "failures": failures,
    }


def _dry_run(rows: list[dict]) -> dict:
    sign = 0
    duplicate = 0
    auto = 0
    complete = 0
    changed = []
    examples = []
    for row in rows:
        raw = row.get("rel") or row["file"]
        path = Path(raw)
        if not path.is_file():
            path = DATA / row["file"]
        if not path.is_file():
            examples.append({"file": row["file"], "reason": "FILE_MISSING"})
            continue
        before = sha256_file(path)
        index = index_hwpx_structure(path)
        if index.analysis_status == "COMPLETE":
            complete += 1
        fields = assess_fields(index)
        keys: dict[tuple, int] = {}
        for field in fields:
            if field.decision != "AUTO":
                continue
            auto += 1
            key = (field.section_index, field.table_index, field.row, field.col)
            keys[key] = keys.get(key, 0) + 1
            if _sign_consent_label(re.sub(r"\s+", "", field.field_label or "")) or _unsafe_label(field.field_label or "") == "CHOICE_MARK":
                sign += 1
                if len(examples) < 20:
                    examples.append({"file": path.name, "reason": "SIGN_CONSENT_AUTO", "label": field.field_label})
        for key, count in keys.items():
            if count > 1:
                duplicate += count
                if len(examples) < 20:
                    examples.append({"file": path.name, "reason": "DUPLICATE_TARGET_LINK", "row": key[2], "col": key[3], "count": count})
        if sha256_file(path) != before:
            changed.append(path.name)
    return {
        "files": len(rows),
        "complete": complete,
        "auto": auto,
        "sign_consent_auto": sign,
        "duplicate_target_link": duplicate,
        "sha_changed": changed,
        "examples": examples,
    }


def main() -> int:
    holdout = json.loads((DATA / "holdout_validation_results.json").read_text(encoding="utf-8"))
    summary = json.loads((DATA / "dry_run_367_summary.json").read_text(encoding="utf-8"))
    holdout_report = _holdout(holdout["FILES"])
    dry_report = _dry_run(_load_form_rows(summary))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "holdout_recheck.json").write_text(json.dumps(holdout_report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "dry_run_recheck.json").write_text(json.dumps(dry_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "HOLDOUT_UNSAFE_AUTO_COUNT": holdout_report["unsafe_auto_count"],
        "HOLDOUT_HIGH_RISK": holdout_report["high_risk"],
        "HOLDOUT_FAIL": holdout_report["fail"],
        "DRY_FILES": dry_report["files"],
        "DRY_COMPLETE": dry_report["complete"],
        "DRY_AUTO": dry_report["auto"],
        "SIGN_CONSENT_AUTO": dry_report["sign_consent_auto"],
        "DUPLICATE_TARGET_LINK": dry_report["duplicate_target_link"],
        "SHA_CHANGED": dry_report["sha_changed"],
    }, ensure_ascii=False, indent=2))
    return 0 if holdout_report["unsafe_auto_count"] == 0 and dry_report["sign_consent_auto"] == 0 and dry_report["duplicate_target_link"] == 0 and not dry_report["sha_changed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
