# -*- coding: utf-8 -*-
"""STEP 2 extraction baseline runner (read-only).

현재 auto_write가 실제 사업계획서에서 무엇을 읽고, 무엇을 구조화하고,
어디서 출처를 잃는지 Golden JSON과 비교해 측정한다.

중요:
- 새 추출기를 만들지 않는다.
- LLM으로 누락값을 보완하지 않는다.
- 기존 production 경로만 재사용한다.
- 실제 고객/개인 문서와 Golden JSON은 GitHub에 커밋하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
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
    "EXTRACT_ERROR": "현재 추출기 실행 중 오류",
    "PARTIAL_INGEST": "문서 전체가 아니라 일부/미리보기 텍스트만 읽었을 가능성이 있음",
    "READ_MISS": "원문을 읽지 못했거나 Golden의 기대 원문 단서를 찾지 못함",
    "VALUE_ERROR": "구조화한 값이 Golden 정답과 다름",
    "CLASSIFY_MISS": "원문에는 값이 있으나 현재 구조화 파서가 해당 필드로 분류하지 못함",
    "SOURCE_LOST": "값은 맞게 구조화했지만 실제 출처 위치를 보존하지 못함",
    "STRUCTURED_EXTRACTION_MISSING": "해당 항목의 구조화 추출 기능이 현재 production 경로에 없음",
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

# 현재 production company_extract가 실제로 구조화할 수 있는 Golden 필드만 연결한다.
# 없는 기능을 Baseline 도구 안에서 새로 구현하지 않는다.
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

_PARTIAL_NOTE_MARKERS = (
    "prvtext",
    "미리보기 텍스트",
    "본문 일부",
    "일부가 누락",
    "partial",
)


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
    raw_terms: list[str]
    raw_presence: str
    structured_supported: bool
    structured_value: Any
    value_match: bool
    source_location_preserved: bool
    status: str
    status_ko: str
    detail: str
    source_file: str
    source_location_expected: str


def _norm_text(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[\s,·._\-–—:/()\[\]{}]+", "", text)


def _raw_terms_for(assertion: dict[str, Any]) -> list[str]:
    """원문 읽기 여부를 확인할 텍스트 단서를 반환한다.

    복합값(dict/list)은 정규화된 숫자와 원문 표기가 다를 수 있으므로 추측하지 않는다.
    Golden에 raw_terms를 명시한 경우에만 검사한다.
    """
    explicit = assertion.get("raw_terms")
    if explicit is not None:
        if not isinstance(explicit, list):
            raise ValueError(f"{assertion.get('id','')}: raw_terms는 array여야 합니다.")
        return [str(v) for v in explicit if str(v).strip()]

    expected = assertion.get("value")
    behavior = str(assertion.get("expected_behavior", ""))
    if behavior not in RAW_PROBE_BEHAVIORS:
        return []
    if expected is None or isinstance(expected, (dict, list, tuple)):
        return []
    return [str(expected)]


def _raw_contains_all(text: str, terms: list[str]) -> bool | None:
    if not terms:
        return None
    haystack = _norm_text(text)
    return all(_norm_text(term) in haystack for term in terms if _norm_text(term))


def _structured_company_value(
    field: str,
    parsed_company: dict[str, dict[str, str]],
) -> Any:
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


def _is_partial_ingest(notes: list[str]) -> bool:
    combined = " ".join(str(note).lower() for note in notes)
    return any(marker in combined for marker in _PARTIAL_NOTE_MARKERS)


def evaluate_assertion(
    assertion: dict[str, Any],
    *,
    source_file: str,
    raw_text: str,
    parsed_company: dict[str, dict[str, str]],
) -> AssertionResult:
    category = str(assertion.get("category", ""))
    field = str(assertion.get("field", ""))
    expected = assertion.get("value")
    raw_terms = _raw_terms_for(assertion)
    raw_check = _raw_contains_all(raw_text, raw_terms)

    structured_supported = category == "COMPANY" and field in COMPANY_FIELD_MAP
    structured_value = (
        _structured_company_value(field, parsed_company)
        if structured_supported
        else None
    )
    value_match = (
        _same_value(expected, structured_value)
        if structured_value is not None
        else False
    )

    # 현재 company_extract 결과에는 실제 page/section/paragraph locator가 없다.
    source_location_preserved = False

    if raw_check is False:
        status = "READ_MISS"
        detail = "Golden이 지정한 원문 단서를 현재 canonical ingest 텍스트에서 모두 찾지 못했습니다."
    elif structured_supported:
        if structured_value is None:
            status = "CLASSIFY_MISS"
            detail = (
                "원문 단서는 확인됐거나 raw 검사가 생략됐지만, "
                "현재 회사 필드 파서가 값을 구조화하지 못했습니다."
            )
        elif not value_match:
            status = "VALUE_ERROR"
            detail = f"현재 구조화 값={structured_value!r}"
        elif not source_location_preserved:
            status = "SOURCE_LOST"
            detail = "구조화 값은 Golden과 일치하지만 실제 source location이 결과에 없습니다."
        else:
            status = "PASS"
            detail = "값과 출처 위치가 모두 Golden 계약을 충족합니다."
    else:
        status = "STRUCTURED_EXTRACTION_MISSING"
        if raw_check is True:
            detail = (
                "원문 단서는 현재 ingest 텍스트에 있으나, "
                "이 category/field를 구조화하는 production extractor가 없습니다."
            )
        else:
            detail = (
                "현재 production 구조화 extractor가 없고, Golden raw_terms도 없어 "
                "원문 존재 여부는 별도로 판정하지 않았습니다."
            )

    raw_presence = (
        "FOUND" if raw_check is True
        else "MISSING" if raw_check is False
        else "SKIPPED"
    )
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
        expected_behavior=str(assertion.get("expected_behavior", "")),
        expected_behavior_ko=str(assertion.get("expected_behavior_ko", "")),
        expected=expected,
        raw_terms=raw_terms,
        raw_presence=raw_presence,
        structured_supported=structured_supported,
        structured_value=structured_value,
        value_match=value_match,
        source_location_preserved=source_location_preserved,
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


def _validate_golden(golden: dict[str, Any]) -> None:
    documents = golden.get("documents")
    assertions = golden.get("assertions")
    if not isinstance(documents, dict) or not isinstance(assertions, list):
        raise ValueError("Golden JSON에 documents(object), assertions(array)가 필요합니다.")

    ids: set[str] = set()
    for assertion in assertions:
        if not isinstance(assertion, dict):
            raise ValueError("Golden assertions의 각 항목은 object여야 합니다.")
        aid = str(assertion.get("id", "")).strip()
        doc_id = str(assertion.get("doc", "")).strip()
        if not aid:
            raise ValueError("Golden assertion에 id가 필요합니다.")
        if aid in ids:
            raise ValueError(f"Golden assertion id 중복: {aid}")
        ids.add(aid)
        if doc_id not in documents:
            raise ValueError(f"{aid}: 존재하지 않는 document id={doc_id}")
        _raw_terms_for(assertion)


def run_baseline(
    golden: dict[str, Any],
    resolved_files: dict[str, Path | None],
    *,
    extractor: Callable[[str | Path], tuple[str, list[str]]] = extract_text,
    company_parser: Callable[[str], dict[str, dict[str, str]]] = parse_company_fields,
) -> dict[str, Any]:
    _validate_golden(golden)

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
                        raw_terms=_raw_terms_for(assertion),
                        raw_presence="SKIPPED",
                        structured_supported=False,
                        structured_value=None,
                        value_match=False,
                        source_location_preserved=False,
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

        if not raw_text.strip():
            doc_status = "EXTRACT_ERROR"
        elif _is_partial_ingest(notes):
            doc_status = "PARTIAL_INGEST"
        else:
            doc_status = "PASS"

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
    raw_counts = Counter(row.raw_presence for row in results)
    total = len(results)
    structured_supported = [row for row in results if row.structured_supported]
    structured_matches = [row for row in structured_supported if row.value_match]
    structured_mismatches = [
        row for row in structured_supported
        if row.structured_value is not None and not row.value_match
    ]
    structured_missing = [
        row for row in structured_supported
        if row.structured_value is None
    ]
    full_pass = counts.get("PASS", 0)

    raw_probed = raw_counts.get("FOUND", 0) + raw_counts.get("MISSING", 0)
    raw_found = raw_counts.get("FOUND", 0)

    return {
        "schema_version": 2,
        "generated_at": datetime.now().astimezone().isoformat(),
        "golden_name": golden.get("name", ""),
        "purpose": "현재 auto_write STEP 2 추출 능력의 읽기전용 baseline 측정",
        "principle": (
            "못 찾음은 허용할 수 있지만 틀리게 확정하는 것은 FAIL. "
            "미구현 기능은 추측하지 않고 미구현으로 표시."
        ),
        "summary": {
            "assertions_total": total,
            "full_contract_pass": full_pass,
            "raw_probe": {
                "probed": raw_probed,
                "found": raw_found,
                "missing": raw_counts.get("MISSING", 0),
                "skipped": raw_counts.get("SKIPPED", 0),
                "found_rate": round(raw_found / raw_probed, 4) if raw_probed else None,
            },
            "structured": {
                "supported": len(structured_supported),
                "value_match": len(structured_matches),
                "value_mismatch": len(structured_mismatches),
                "value_missing": len(structured_missing),
                "unsupported": total - len(structured_supported),
            },
            "source": {
                "value_matches_requiring_source": len(structured_matches),
                "source_preserved": sum(
                    1 for row in structured_matches if row.source_location_preserved
                ),
            },
            "by_status": dict(sorted(counts.items())),
        },
        "metrics": {
            "critical_fact_precision": "MEASUREMENT_NOT_IMPLEMENTED",
            "critical_numeric_recall": "MEASUREMENT_NOT_IMPLEMENTED",
            "section_classification_recall": "MEASUREMENT_NOT_IMPLEMENTED",
            "source_link_rate": (
                0.0 if structured_matches else "MEASUREMENT_NOT_IMPLEMENTED"
            ),
            "note_ko": (
                "전체 사업계획서 구조화 extractor가 아직 없어 최종 Precision/Recall은 계산하지 않습니다. "
                "대신 현재 단계에서 실제로 측정 가능한 원문 단서 발견률, 기존 구조화 지원/값 일치, "
                "출처 보존 여부를 분리해 표시합니다."
            ),
        },
        "documents": documents_report,
        "results": [asdict(row) for row in results],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    raw = summary["raw_probe"]
    structured = summary["structured"]
    source = summary["source"]

    found_rate = (
        f"{raw['found_rate'] * 100:.1f}%"
        if isinstance(raw.get("found_rate"), (int, float))
        else "측정 대상 없음"
    )

    lines = [
        "# STEP 2 추출 Baseline 결과",
        "",
        f"- 전체 Golden 항목: **{summary['assertions_total']}개**",
        f"- 원문 단서 검사: **{raw['found']}/{raw['probed']} 발견 ({found_rate})**",
        f"- 원문 검사 생략: **{raw['skipped']}개** — 복합값은 Golden `raw_terms`가 없으면 추측하지 않음",
        f"- 현재 구조화 지원: **{structured['supported']}개**",
        f"- 구조화 값 일치: **{structured['value_match']}개**",
        f"- 구조화 값 불일치: **{structured['value_mismatch']}개**",
        f"- 구조화 값 누락: **{structured['value_missing']}개**",
        f"- 구조화 기능 미지원: **{structured['unsupported']}개**",
        f"- 값 일치 후 출처 위치까지 보존: **{source['source_preserved']}/{source['value_matches_requiring_source']}개**",
        f"- 전체 계약 PASS: **{summary['full_contract_pass']}개**",
        "",
        "## 핵심 해석",
        "",
        "- **원문 단서 발견률**: 현재 HWP/HWPX/DOCX/PDF ingest가 Golden 단서를 텍스트로 보존했는지 보는 1차 지표입니다.",
        "- **구조화 값 일치**: 현재 production 구조화 파서가 지원하는 항목만 평가합니다.",
        "- **전체 계약 PASS**: 값뿐 아니라 출처 위치까지 보존해야 PASS입니다.",
        "- ACTUAL/PLAN/CONFLICT 자동 판정은 현재 production 구조화 결과가 없으므로 아직 별도 Precision/Recall로 계산하지 않습니다.",
        "",
        "## 오류/미구현 요약",
        "",
        "| 코드 | 한글 설명 | 건수 |",
        "|---|---|---:|",
    ]
    for code, count in summary["by_status"].items():
        lines.append(f"| `{code}` | {ERROR_KO.get(code, code)} | {count} |")

    lines.extend([
        "",
        "## 문서 읽기 상태",
        "",
        "| 문서 | 상태 | 추출 글자수 | 구조화된 기업 필드 |",
        "|---|---|---:|---|",
    ])
    for doc_id, doc in report["documents"].items():
        fields = ", ".join(doc.get("company_fields") or []) or "-"
        lines.append(
            f"| {doc_id} · {doc.get('name','')} | "
            f"`{doc.get('status','')}` · {doc.get('status_ko','')} | "
            f"{doc.get('text_chars',0)} | {fields} |"
        )

    lines.extend([
        "",
        "## 항목별 결과",
        "",
        "| ID | 구분 | 항목 | 기대 상태 | 원문 검사 | 결과 | 설명 |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in report["results"]:
        detail = str(row.get("detail", "")).replace("|", "\\|").replace("\n", " ")
        raw_text = row.get("raw_presence", "")
        raw_terms = row.get("raw_terms") or []
        if raw_terms:
            raw_text += " · " + ", ".join(str(v) for v in raw_terms)
        lines.append(
            f"| {row['assertion_id']} | {row['category_ko']} | "
            f"{row['field_ko']} (`{row['field']}`) | "
            f"{row.get('semantic_state_ko') or row.get('semantic_state','')} | "
            f"{raw_text} | `{row['status']}` · {row['status_ko']} | {detail} |"
        )

    lines.extend([
        "",
        "## 코드 설명",
        "",
        "- `PARTIAL_INGEST` — HWP 미리보기(PrvText) 등 일부 텍스트만 읽었을 가능성이 있어 전체 Baseline을 신뢰하면 안 됩니다.",
        "- `READ_MISS` — Golden의 원문 단서를 ingest 단계에서 잃었습니다. 구조화 로직보다 먼저 고칠 대상입니다.",
        "- `STRUCTURED_EXTRACTION_MISSING` — 원문을 못 읽었다는 뜻이 아니라 해당 항목의 구조화 extractor가 아직 없다는 뜻입니다.",
        "- `SOURCE_LOST` — 값은 맞지만 파일 내 실제 위치(page/section/table/cell 등)를 보존하지 못했습니다.",
        "- 실제 고객/개인 문서와 Golden JSON은 GitHub에 커밋하지 않습니다.",
        "",
    ])
    return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Golden JSON 최상위는 object여야 합니다.")
    _validate_golden(data)
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="현재 auto_write STEP 2 추출 능력을 Golden JSON과 비교합니다 (원본 읽기전용)."
    )
    parser.add_argument(
        "--golden",
        required=True,
        help="로컬 Golden JSON 경로 (실제 개인정보 포함 가능, Git 커밋 금지)",
    )
    parser.add_argument(
        "--input-dir",
        help="Golden documents의 파일명이 들어 있는 폴더",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="검사할 파일 경로. 여러 번 지정 가능; Golden 파일명으로 매칭",
    )
    parser.add_argument(
        "--out-dir",
        default="results/step2_extraction_baseline",
        help="결과 저장 폴더",
    )
    args = parser.parse_args(argv)

    golden_path = Path(args.golden).expanduser().resolve()
    if not golden_path.is_file():
        print(f"Golden JSON을 찾지 못했습니다: {golden_path}", file=sys.stderr)
        return 2

    try:
        golden = _load_json(golden_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Golden JSON 오류: {exc}", file=sys.stderr)
        return 2

    input_dir = Path(args.input_dir).expanduser().resolve() if args.input_dir else None
    explicit_files = [Path(p).expanduser().resolve() for p in args.file]
    resolved = _resolve_document_paths(
        golden,
        input_dir=input_dir,
        explicit_files=explicit_files,
    )
    report = run_baseline(golden, resolved)

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / "baseline_report.json"
    md_out = out_dir / "baseline_report.md"
    json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_out.write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    raw = summary["raw_probe"]
    structured = summary["structured"]

    print("\n=== STEP 2 추출 Baseline ===")
    print(
        f"전체 {summary['assertions_total']}개 | "
        f"원문 단서 {raw['found']}/{raw['probed']} 발견 | "
        f"구조화 지원 {structured['supported']}개 | "
        f"값 일치 {structured['value_match']}개 | "
        f"전체 계약 PASS {summary['full_contract_pass']}개"
    )
    for code, count in summary["by_status"].items():
        print(f"- {code}: {ERROR_KO.get(code, code)} — {count}건")
    print(f"\nJSON: {json_out}")
    print(f"한글 리포트: {md_out}")

    # 문서 자체를 못 읽었거나 일부 미리보기만 읽은 경우에는
    # 리포트는 남기되 baseline 실행을 성공으로 종료하지 않는다.
    fatal = any(
        doc.get("status") in {"FILE_MISSING", "EXTRACT_ERROR", "PARTIAL_INGEST"}
        for doc in report["documents"].values()
    )
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
