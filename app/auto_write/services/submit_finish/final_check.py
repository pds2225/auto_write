"""F7-A 구조·기술 검증: 기존 게이트를 호출만 하고 Finding 으로 통일한다(재구현 없음).

재사용: hwpx_integrity_gate(구조+수용검사), hwpx_form_diff(양식 생존),
        status.Finding. L규칙 3단계·R9 는 integrity gate / lrule 계열이 정본이며
        여기서는 결과 집계만 한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .status import Finding, Status, sanitize_forbidden

_SEVERITY_TO_STATUS = {
    "PASS": Status.PASS,
    "WARNING": Status.REVIEW,
    "REVIEW_REQUIRED": Status.REVIEW,
    "HARD_FAIL": Status.FAIL,
}


def _mk(code: str, status: Status, message: str, evidence: str = "", **meta: Any) -> Finding:
    return Finding(
        code=code,
        status=status,
        message=sanitize_forbidden(message),
        source="structural",
        evidence=sanitize_forbidden(evidence),
        meta=meta,
    )


def check_hwpx_structure(
    hwpx: str | Path,
    *,
    baseline_form: str | Path | None = None,
    allowed_names: tuple[str, ...] = (),
    expected_phrase_edits: int = 0,
) -> list[Finding]:
    """HWPX 구조·수용검사(R9 보호영역·무결성 포함 게이트)와 양식 생존 비교를 실행한다."""
    from auto_write.services.hwpx_integrity_gate import EXECUTED, run_hwpx_integrity_gate

    findings: list[Finding] = []
    try:
        report = run_hwpx_integrity_gate(
            str(hwpx),
            allowed_names=allowed_names,
            acceptance_baseline=str(baseline_form) if baseline_form else None,
        )
    except Exception as exc:  # 게이트 자체 장애는 숨기지 않고 미실행으로 보존
        return [_mk("STRUCT_GATE_ERROR", Status.UNVERIFIED, "기술적 검증 미실행", f"{type(exc).__name__}: {exc}")]

    for res in report.validators:
        if res.validator_status != EXECUTED:
            findings.append(_mk(f"STRUCT_{res.source_validator}", Status.UNVERIFIED,
                                f"기술적 검증 미실행({res.validator_status})", res.message))
            continue
        status = _SEVERITY_TO_STATUS.get(res.severity, Status.REVIEW)
        label = {Status.PASS: "자동 검사 PASS", Status.FAIL: "구조 검사 FAIL"}.get(status, "사용자 확인 필요")
        findings.append(_mk(f"STRUCT_{res.source_validator}", status, f"{label}: {res.source_validator}",
                            res.message or res.defect_code, defect_code=res.defect_code))

    if baseline_form:
        try:
            from auto_write.services.hwpx_form_diff import compare_hwpx_forms

            diff = compare_hwpx_forms(baseline_form, hwpx)
            edits = getattr(diff, "form_phrase_edits", 0)
            only_expected_edits = (not diff.form_intact and not diff.structure_deltas
                                   and not getattr(diff, "form_phrase_drops", 0)
                                   and 0 < edits <= expected_phrase_edits)
            if diff.form_intact:
                findings.append(_mk("FORM_INTACT", Status.PASS, "자동 검사 PASS: 원본 양식 구조 유지"))
            elif only_expected_edits:
                # 이름 기입 등 우리가 의도해 넣은 값 때문에 양식 문구가 바뀐 경우: 건수가 일치할 때만 확인 요청으로 낮춘다.
                findings.append(_mk("FORM_INTACT", Status.REVIEW,
                                    f"사용자 확인 필요: 값 기입으로 양식 문구 {edits}건 변경(구조 변화 없음, 삭제 없음)",
                                    f"기대 변경 {expected_phrase_edits}건 이내"))
            else:
                findings.append(_mk("FORM_INTACT", Status.FAIL, "구조 검사 FAIL: 원본 양식 구조 변경",
                                    f"deltas={diff.structure_deltas} edits={edits}"))
        except Exception as exc:
            findings.append(_mk("FORM_INTACT", Status.UNVERIFIED, "기술적 검증 미실행", f"{type(exc).__name__}: {exc}"))
    return findings


def summarize(findings: list[Finding]) -> dict[str, Any]:
    """상태별 건수와 사용자 확인 목록(REVIEW/UNVERIFIED)을 만든다. 제출 여부는 판단하지 않는다."""
    counts = {s.value: 0 for s in Status}
    for f in findings:
        counts[f.status.value] += 1
    return {
        "counts": counts,
        "user_review_list": [f.to_dict() for f in findings if f.status in (Status.REVIEW, Status.UNVERIFIED)],
        "fail_list": [f.to_dict() for f in findings if f.status is Status.FAIL],
    }


def should_block_submission_named_pdf(findings: list[Finding]) -> bool:
    """12장: 기술적 FAIL 로 정상 산출물을 보장할 수 없으면 '(제출)' 명칭 PDF 자동 생성을 중단한다.

    이는 엔진의 산출물 생성 통제이며 제출 여부 판단이 아니다. REVIEW 는 차단 조건이 아니다.
    structural 출처의 FAIL 만 대상이다(시각 AI 의 의심은 사용자 확인 목록으로만 간다).
    """
    return any(f.status is Status.FAIL and f.source in ("structural", "engine") for f in findings)
