# -*- coding: utf-8 -*-
"""STEP 2 extraction baseline runner (read-only).

Measures what the *current* auto_write extraction stack can recover from real
business-plan files without adding a new extractor. It combines:

1) canonical raw ingest: auto_write.services.doc_text_extract.extract_text
2) existing company-field parser: auto_write.services.company_extract.parse_company_fields
3) a local Golden JSON supplied by the user (kept outside Git when it contains
   real customer/personal data)

The runner never modifies input documents and never asks an LLM to fill missing
facts. Unsupported structured categories are reported as NOT_IMPLEMENTED rather
than guessed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.services.doc_text_extract import extract_text  # noqa: E402
from auto_write.services.company_extract import parse_company_fields  # noqa: E402

ERROR_KO = {
    "PASS": "정상",
    "FILE_MISSING": "입력 파일을 찾지 못함",
    "READ_MISS": "원문을 읽지 못했거나 기대 값이 추출 텍스트에 없음",
    "VALUE_ERROR": "값을 잘못 추출함",
    "CLASSIFY_MISS": "내용을 잘못된 항목으로 분류함",
    "ACTUAL_PLAN_ERROR": "향후 계획과 현재 사실·실적을 혼동함",
    "SOURCE_LOST": "값은 찾았지만 출처 위치를 보존하지 못함",
    "CONFLICT_MISS": "충돌하는 정보를 충돌로 인식하지 못함",
    "STRUCTURED_EXTRACTION_MISSING": "해당 항목의 구조화 추출 기능이 현재 production 경로에 없음",
    "RAW_CHECK_SKIPPED": "원문 존재 여부를 기계적으로 비교하기 어려운 서술형 항목",
    "EXTRACT_ERROR": "현재 추출기 실행 중 오류",
}

SEMANTIC_KO = {
    "ACTUAL": "현재 사실·실적",
    "PLAN": "향후 계획",
    "ESTIMATE": "추정·산정값",
    "HYPOTHESIS": "가설",
    "UNKNOWN": "알 수 없음/자료 부족",
    "NOT_APPLICABLE": "해당 없음",
    "CONFLICT": "서로 충돌하는 정보",
}

# Current production structured extractor only supports a small company-identity
# surface. This adapter maps Golden field names to the existing canonical labels.
COMPANY_FIELD_MAP = {
    "applicant_name": "대표자",
    "representative_name": "대표자",
    "business_location": "주소",
    "industry": "업종",
}

RAW_PROBE_BEHAVIORS = {
    "extract_exact",
    "extract_number_exact",
    "extract_status_exact",
    "extract_status_and_date",
    "preserve_approximation",
}


@dataclass
class AssertionResult:
    assertion_id: str
    document_id: str
    category: str
    category_ko: str
    field: str
    field_ko: str
    semantic_state: str
    semantic_state_ko: str
    verification_state: str
    verification_state_ko: str
    expected_behavior: str
    expected_behavior_ko: str
    expected: Any
    structured_value: Any
    value_match: bool
    raw_presence: str
    status: str
    status_ko: str
    detail: str
    source_file: str
    source_location_expected: str


def _norm_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[\s,·._\-–—:/()\[\]{}]+", "", text)
    return text


def _raw_contains(text: str, expected: Any) -> bool | None:
    if expected is None:
        return None
    if isinstance(expected, (dict, list, tuple)):
        return None
    needle = _norm_text(expected)
    if not needle:
        return None
    return needle in _norm_text(text)


def _structured_company_value(field: str, parsed_company: dict[str, dict[str, str]]) -> Any:
    canon = COMPANY_FIELD_MAP.get(field)
    if not canon:
        return None
    value = parsed_company.get(canon)
    if not isinstance(value, dict):
        return None
    return value.get("value")


def _same_value(expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    return _norm_text(expected) == _norm_text(actual)


def evaluate_assertion(
    assertion: dict[str, Any],
    *,
    source_file: str,
    raw_text: str,
    parsed_company: dict[str, dict[str, str]],
) -> AssertionResult:
    category = str(assertion.get("category", ""))
    field = str(assertion.get("field", ""))
    behavior = str(assertion.get("expected_behavior", ""))
    expected = assertion.get("value")

    structured_value = None
    structured_supported = category == "COMPANY" and field in COMPANY_FIELD_MAP
    if structured_supported:
        structured_value = _structured_company_value(field, parsed_company)

    raw_check: bool | None = None
    if behavior in RAW_PROBE_BEHAVIORS:
        raw_check = _raw_contains(raw_text, expected)

    if structured_supported:
        if structured_value is None:
            status = "READ_MISS" if raw_check is False else "CLASSIFY_MISS"
            detail = (
                "원문에도 기대값이 보이지 않습니다." if raw_check is False
                else "원문에는 값이 있을 수 있으나 현재 회사 필드 파서가 구조화하지 못했습니다."
            )
        elif _same_value(expected, structured_value):
            # 값 자체는 맞지만 현재 parser 결과에는 실제 page/section/paragraph locator가 없다.
            # Golden contract는 source link까지 요구하므로 전체 PASS로 부풀리지 않는다.
            status = "SOURCE_LOST"
            detail = "구조화 값은 Golden과 일치하지만 현재 추출 결과에 실제 source location이 없습니다."
        else:
            status = "VALUE_ERROR"
            detail = f"현재 구조화 값={structured_value!r}"
    else:
        if raw_check is False:
            status = "READ_MISS"
            detail = "현재 canonical ingest 텍스트에서 기대값을 찾지 못했습니다."
        else:
            status = "STRUCTURED_EXTRACTION_MISSING"
            if raw_check is True:
                detail = "원문 텍스트에는 기대값이 있으나 이 category/field를 구조화하는 production extractor가 없습니다."
            else:
                detail = "현재 production 구조화 extractor가 없으며, 서술형이라 raw exact 비교도 생략했습니다."

    raw_presence = "FOUND" if raw_check is True else "MISSING" if raw_check is False else "SKIPPED"
    return AssertionResult(
        assertion_id=str(assertion.get("id", "")),
        document_id=str(assertion.get("doc", "")),
        category=category,
        category_ko=str(assertion.get("category_ko") or category),
        field=field,
        field_ko=str(assertion.get("field_ko") or field),
        semantic_state=str(assertion.get("semantic_state", "")),
        semantic_state_ko=str(
            assertion.get("semantic_state_ko")
            or SEMANTIC_KO.get(str(assertion.get("semantic_state", "")), "")
        ),
        verification_state=str(assertion.get("verification_state", "")),
        verification_state_ko=str(assertion.get("verification_state_ko", "")),
        expected_behavior=behavior,
        expected_behavior_ko=str(assertion.get("expected_behavior_ko", "")),
        expected=expected,
        structured_value=structured_value,
        value_match=_same_value(expected, structured_value) if structured_value is not None else False,
        raw_presence=raw_presence,
        status=status,
        status_ko=ERROR_KO[status],
        detail=detail,
        source_file=source_file,
        source_location_expected=str(assertion.get("source_location", "")),
    )


def _resolve_document_paths(
    golden: dict[str, Any],
    *,
    input_dir: Path | None,
    explicit_files: list[Path],
) -> dict[str, Path | None]:
    by_name = {p.name: p for p in explicit_files}
    resolved: dict[str, Path | None] = {}
    for doc_id, meta in (golden.get("documents") or {}).items():
        name = str((meta or {}).get("name", ""))
        candidate = by_name.get(name)
        if candidate is None and input_dir is not None:
            path = input_dir / name
            candidate = path if path.exists() else None
        resolved[str(doc_id)] = candidate
    return resolved


def run_baseline(
    golden: dict[str, Any],
    resolved_files: dict[str, Path | None],
    *,
    extractor: Callable[[str | Path], tuple[str, list[str]]] = extract_text,
    company_parser: Callable[[str], dict[str, dict[str, str]]] = parse_company_fields,
) -> dict[str, Any]:
    assertions_by_doc: dict[str, list[dict[str, Any]]] = {}
    for assertion in golden.get("assertions") or []:
        assertions_by_doc.setdefault(str(assertion.get("doc", "")), []).append(assertion)

    results: list[AssertionResult] = []
    documents_report: dict[str, Any] = {}

    for doc_id, meta in (golden.get("documents") or {}).items():
        path = resolved_files.get(str(doc_id))
        name = str((meta or {}).get("name", ""))
        if path is None or not path.exists():
            documents_report[str(doc_id)] = {
                "name": name,
                "path": str(path or ""),
                "status": "FILE_MISSING",
                "status_ko": ERROR_KO["FILE_MISSING"],
                "text_chars": 0,
                "company_fields": [],
                "notes": [],
            }
            for assertion in assertions_by_doc.get(str(doc_id), []):
                results.append(
                    AssertionResult(
                        assertion_id=str(assertion.get("id", "")),
                        document_id=str(doc_id),
                        category=str(assertion.get("category", "")),
                        category_ko=str(assertion.get("category_ko") or assertion.get("category", "")),
                        field=str(assertion.get("field", "")),
                        field_ko=str(assertion.get("field_ko") or assertion.get("field", "")),
                        semantic_state=str(assertion.get("semantic_state", "")),
                        semantic_state_ko=str(assertion.get("semantic_state_ko") or ""),
                        verification_state=str(assertion.get("verification_state", "")),
                        verification_state_ko=str(assertion.get("verification_state_ko", "")),
                        expected_behavior=str(assertion.get("expected_behavior", "")),
                        expected_behavior_ko=str(assertion.get("expected_behavior_ko", "")),
                        expected=assertion.get("value"),
                        structured_value=None,
                        value_match=False,
                        raw_presence="SKIPPED",
                        status="FILE_MISSING",
                        status_ko=ERROR_KO["FILE_MISSING"],
                        detail="Golden 문서 파일을 찾지 못해 검사하지 못했습니다.",
                        source_file=name,
                        source_location_expected=str(assertion.get("source_location", "")),
                    )
                )
            continue

        try:
            raw_text, notes = extractor(path)
        except Exception as exc:  # noqa: BLE001
            raw_text, notes = "", [f"{type(exc).__name__}: {exc}"]

        parsed_company: dict[str, dict[str, str]] = {}
        if raw_text.strip():
            try:
                parsed_company = company_parser(raw_text)
            except Exception as exc:  # noqa: BLE001
                notes = [*notes, f"company parser error: {type(exc).__name__}: {exc}"]

        doc_status = "PASS" if raw_text.strip() else "EXTRACT_ERROR"
        documents_report[str(doc_id)] = {
            "name": name,
            "path": str(path),
            "status": doc_status,
            "status_ko": ERROR_KO[doc_status],
            "text_chars": len(raw_text),
            "company_fields": sorted(parsed_company.keys()),
            "notes": notes,
        }

        for assertion in assertions_by_doc.get(str(doc_id), []):
            results.append(
                evaluate_assertion(
                    assertion,
                    source_file=name,
                    raw_text=raw_text,
                    parsed_company=parsed_company,
                )
            )

    counts = Counter(row.status for row in results)
    total = len(results)
    passed = counts.get("PASS", 0)
    scored_failures = total - passed
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "golden_name": golden.get("name", ""),
        "purpose": "현재 auto_write STEP 2 추출 능력의 읽기전용 baseline 측정",
        "principle": "못 찾음은 허용할 수 있지만 틀리게 확정하는 것은 FAIL. 미구현 기능은 추측하지 않고 미구현으로 표시.",
        "summary": {
            "assertions_total": total,
            "pass": passed,
            "not_pass": scored_failures,
            "by_status": dict(sorted(counts.items())),
        },
        "metrics": {
            "critical_fact_precision": "MEASUREMENT_NOT_IMPLEMENTED",
            "critical_numeric_recall": "MEASUREMENT_NOT_IMPLEMENTED",
            "section_classification_recall": "MEASUREMENT_NOT_IMPLEMENTED",
            "source_link_rate": "MEASUREMENT_NOT_IMPLEMENTED",
            "note_ko": "현재 production extractor가 전체 사업계획서 구조를 반환하지 않아 정밀도/재현율을 정직하게 계산할 수 없습니다. 추출 기능을 구현한 뒤 같은 Golden으로 측정합니다.",
        },
        "documents": documents_report,
        "results": [asdict(row) for row in results],
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# STEP 2 추출 Baseline 결과",
        "",
        f"- 전체 Golden 항목: **{s['assertions_total']}개**",
        f"- 현재 구조화 PASS: **{s['pass']}개**",
        f"- PASS 아님: **{s['not_pass']}개**",
        "",
        "## 측정 가능한 범위",
        "",
        "- Critical Fact Precision: **MEASUREMENT_NOT_IMPLEMENTED — 아직 전체 구조화 추출 결과가 없어 측정 불가**",
        "- Critical Numeric Recall: **MEASUREMENT_NOT_IMPLEMENTED — 아직 수치 Fact 구조화 추출 결과가 없어 측정 불가**",
        "- Section Classification Recall: **MEASUREMENT_NOT_IMPLEMENTED — 아직 섹션 구조화 추출기가 없어 측정 불가**",
        "- Source Link Rate: **MEASUREMENT_NOT_IMPLEMENTED — 현재 추출기가 실제 page/section locator를 구조화 결과에 보존하지 않음**",
        "",
        "## 오류/미구현 요약",
        "",
        "| 코드 | 한글 설명 | 건수 |",
        "|---|---|---:|",
    ]
    for code, count in s["by_status"].items():
        lines.append(f"| `{code}` | {ERROR_KO.get(code, code)} | {count} |")

    lines.extend(["", "## 문서 읽기 상태", "", "| 문서 | 상태 | 추출 글자수 | 구조화된 기업 필드 |", "|---|---|---:|---|"])
    for doc_id, doc in report["documents"].items():
        fields = ", ".join(doc.get("company_fields") or []) or "-"
        lines.append(f"| {doc_id} · {doc.get('name','')} | {doc.get('status_ko','')} | {doc.get('text_chars',0)} | {fields} |")

    lines.extend([
        "",
        "## 항목별 결과",
        "",
        "| ID | 구분 | 항목 | 기대 상태 | 기대 동작 | 결과 | 설명 |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in report["results"]:
        detail = str(row.get("detail", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {row['assertion_id']} | {row['category_ko']} | {row['field_ko']} "
            f"(`{row['field']}`) | {row.get('semantic_state_ko') or row.get('semantic_state','')} "
            f"| {row.get('expected_behavior_ko') or row.get('expected_behavior','')} "
            f"| `{row['status']}` · {row['status_ko']} | {detail} |"
        )

    lines.extend([
        "",
        "## 해석",
        "",
        "- `STRUCTURED_EXTRACTION_MISSING`은 원문을 못 읽었다는 뜻이 아니라, 현재 production 경로에 그 항목을 구조화하는 추출기가 없다는 뜻입니다.",
        "- `READ_MISS`는 canonical ingest 단계에서 먼저 고쳐야 합니다.",
        "- 이 도구는 Baseline 측정만 하며 원본 HWP/HWPX/DOCX/PDF를 수정하지 않습니다.",
        "- 실제 고객/개인 문서와 Golden 정답 JSON은 GitHub에 커밋하지 마세요.",
        "",
    ])
    return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Golden JSON 최상위는 object여야 합니다.")
    if not isinstance(data.get("documents"), dict) or not isinstance(data.get("assertions"), list):
        raise ValueError("Golden JSON에 documents(object), assertions(array)가 필요합니다.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="현재 auto_write STEP 2 추출 능력을 Golden JSON과 비교합니다 (원본 읽기전용)."
    )
    parser.add_argument("--golden", required=True, help="로컬 Golden JSON 경로 (실제 개인정보 포함 가능, Git 커밋 금지)")
    parser.add_argument("--input-dir", help="Golden documents의 파일명이 들어 있는 폴더")
    parser.add_argument("--file", action="append", default=[], help="검사할 파일 경로. 여러 번 지정 가능; Golden 파일명으로 매칭")
    parser.add_argument("--out-dir", default="results/step2_extraction_baseline", help="결과 저장 폴더")
    args = parser.parse_args(argv)

    golden_path = Path(args.golden).expanduser().resolve()
    if not golden_path.is_file():
        print(f"Golden JSON을 찾지 못했습니다: {golden_path}", file=sys.stderr)
        return 2

    input_dir = Path(args.input_dir).expanduser().resolve() if args.input_dir else None
    explicit_files = [Path(p).expanduser().resolve() for p in args.file]
    golden = _load_json(golden_path)
    resolved = _resolve_document_paths(golden, input_dir=input_dir, explicit_files=explicit_files)
    report = run_baseline(golden, resolved)

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "baseline_report.json"
    md_out = out_dir / "baseline_report.md"
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_out.write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    print("\n=== STEP 2 추출 Baseline ===")
    print(f"전체 {summary['assertions_total']}개 | PASS {summary['pass']}개 | PASS 아님 {summary['not_pass']}개")
    for code, count in summary["by_status"].items():
        print(f"- {code}: {ERROR_KO.get(code, code)} — {count}건")
    print(f"\nJSON: {json_out}")
    print(f"한글 리포트: {md_out}")

    # Baseline is diagnostic: missing capabilities do not make the process exit 1.
    # File/read failures do, because the measurement itself is invalid.
    fatal = any(
        doc.get("status") in {"FILE_MISSING", "EXTRACT_ERROR"}
        for doc in report["documents"].values()
    )
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
