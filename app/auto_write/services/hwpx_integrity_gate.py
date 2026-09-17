"""HWPX 공통 무결성 게이트.

기존 의미검증기와 제출 수용검사기를 하나의 결과 계약으로 묶는다.
검사 결과(PASS/결함)와 검사 실행 상태(EXECUTED/ERROR/TIMEOUT/UNAVAILABLE)를
분리해, 검사 자체가 실패했을 때 정상 통과로 오인되지 않게 한다.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .hwpx_acceptance import run_hwpx_acceptance
from .hwpx_layout_fix import check_hwpx_semantics

PASS = "PASS"
WARNING = "WARNING"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
HARD_FAIL = "HARD_FAIL"

EXECUTED = "EXECUTED"
ERROR = "ERROR"
TIMEOUT = "TIMEOUT"
UNAVAILABLE = "UNAVAILABLE"

_SEVERITY_RANK = {
    PASS: 0,
    WARNING: 1,
    REVIEW_REQUIRED: 2,
    HARD_FAIL: 3,
}


def _environment() -> dict[str, str]:
    """민감정보 없이 validator 실행환경을 남긴다."""
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }


def _payload_dict(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, Mapping):
        return dict(payload)
    as_dict = getattr(payload, "as_dict", None)
    if callable(as_dict):
        result = as_dict()
        return dict(result) if isinstance(result, Mapping) else None
    return None


@dataclass
class ValidatorResult:
    """한 validator의 실행상태와 판정 결과."""

    source_validator: str
    validator_status: str
    severity: str
    message: str = ""
    defect_code: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_validator": self.source_validator,
            "validator_status": self.validator_status,
            "severity": self.severity,
            "message": self.message,
            "defect_code": self.defect_code,
            "evidence": dict(self.evidence),
        }


@dataclass
class IntegrityGateReport:
    """여러 validator를 집계한 공통 gate 결과."""

    source: str
    validators: list[ValidatorResult] = field(default_factory=list)

    @property
    def final_status(self) -> str:
        if not self.validators:
            return HARD_FAIL
        return max(self.validators, key=lambda item: _SEVERITY_RANK[item.severity]).severity

    @property
    def ok(self) -> bool:
        return self.final_status == PASS

    @property
    def acceptance_report(self) -> dict[str, Any]:
        """기존 SubmitReport 호환용 acceptance 결과를 돌려준다."""
        for result in self.validators:
            if result.source_validator != "run_hwpx_acceptance":
                continue
            report = dict(result.evidence.get("report") or {})
            if result.validator_status != EXECUTED:
                report.setdefault("ok", False)
                report.setdefault("exception", result.evidence.get("exception", result.message))
            return report
        return {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "ok": self.ok,
            "final_status": self.final_status,
            "validators": [result.as_dict() for result in self.validators],
        }


def _execution_failure(
    *,
    source_validator: str,
    status: str,
    severity: str,
    exc: BaseException,
) -> ValidatorResult:
    failure_code = f"{source_validator.upper()}_{status}"
    return ValidatorResult(
        source_validator=source_validator,
        validator_status=status,
        severity=severity,
        message=f"{source_validator} 실행 실패: {type(exc).__name__}: {exc}",
        defect_code=failure_code,
        evidence={
            "failure_code": failure_code,
            "exception": f"{type(exc).__name__}: {exc}",
            "environment": _environment(),
        },
    )


def _run_structural_validator(
    source_validator: str,
    validator: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> ValidatorResult:
    """구조 validator 실행. 실행 실패는 항상 HARD_FAIL이다."""
    try:
        payload = validator(*args, **kwargs)
    except TimeoutError as exc:
        return _execution_failure(
            source_validator=source_validator,
            status=TIMEOUT,
            severity=HARD_FAIL,
            exc=exc,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        return _execution_failure(
            source_validator=source_validator,
            status=UNAVAILABLE,
            severity=HARD_FAIL,
            exc=exc,
        )
    except Exception as exc:  # noqa: BLE001 - gate는 silent PASS를 금지한다.
        return _execution_failure(
            source_validator=source_validator,
            status=ERROR,
            severity=HARD_FAIL,
            exc=exc,
        )

    data = _payload_dict(payload)
    if data is None or "ok" not in data:
        exc = ValueError("validator 결과에 ok 필드가 없습니다")
        return _execution_failure(
            source_validator=source_validator,
            status=ERROR,
            severity=HARD_FAIL,
            exc=exc,
        )

    evidence: dict[str, Any] = {"report": data}
    if data.get("ok"):
        # acceptance validator가 XML 파싱 실패를 notes에만 남기던 기존 동작을
        # 정상 통과로 취급하지 않는다.
        notes = data.get("notes") or []
        parse_failures = [note for note in notes if "파싱 실패" in str(note)]
        if parse_failures:
            failure_code = f"{source_validator.upper()}_PARSE_ERROR"
            evidence.update({
                "failure_code": failure_code,
                "environment": _environment(),
                "notes": parse_failures,
            })
            return ValidatorResult(
                source_validator=source_validator,
                validator_status=ERROR,
                severity=HARD_FAIL,
                message="검사 대상 XML을 파싱하지 못했습니다.",
                defect_code=failure_code,
                evidence=evidence,
            )
        return ValidatorResult(
            source_validator=source_validator,
            validator_status=EXECUTED,
            severity=PASS,
            message="검사 결과 결함 없음",
            evidence=evidence,
        )

    return ValidatorResult(
        source_validator=source_validator,
        validator_status=EXECUTED,
        severity=HARD_FAIL,
        message="구조 또는 제출 무결성 결함이 발견되었습니다.",
        defect_code=f"{source_validator.upper()}_FAILED",
        evidence=evidence,
    )


def _run_render_validator(
    path: str,
    validator: Callable[[str], Any] | None,
) -> ValidatorResult | None:
    """선택적으로 렌더링 validator를 실행한다.

    현재 저장소에는 한글 렌더러를 항상 호출하는 공통 함수가 없으므로,
    호출자가 실제 smoke validator를 제공한 경우에만 실행한다.
    제공된 렌더 validator의 실행 실패는 REVIEW_REQUIRED로 집계한다.
    """
    if validator is None:
        return None
    try:
        payload = validator(path)
    except TimeoutError as exc:
        return _execution_failure(
            source_validator="rendering_validator",
            status=TIMEOUT,
            severity=REVIEW_REQUIRED,
            exc=exc,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        return _execution_failure(
            source_validator="rendering_validator",
            status=UNAVAILABLE,
            severity=REVIEW_REQUIRED,
            exc=exc,
        )
    except Exception as exc:  # noqa: BLE001 - rendering 실패는 silent PASS 금지.
        return _execution_failure(
            source_validator="rendering_validator",
            status=ERROR,
            severity=REVIEW_REQUIRED,
            exc=exc,
        )

    data = _payload_dict(payload)
    if data is None or "ok" not in data:
        exc = ValueError("rendering validator 결과에 ok 필드가 없습니다")
        return _execution_failure(
            source_validator="rendering_validator",
            status=ERROR,
            severity=REVIEW_REQUIRED,
            exc=exc,
        )
    ok = bool(data.get("ok"))
    severity = data.get("severity") if data.get("severity") in _SEVERITY_RANK else (PASS if ok else REVIEW_REQUIRED)
    return ValidatorResult(
        source_validator="rendering_validator",
        validator_status=EXECUTED,
        severity=severity,
        message=str(data.get("message") or ("렌더링 smoke 통과" if ok else "렌더링 검토 필요")),
        defect_code=str(data.get("defect_code") or ("" if ok else "RENDERING_REVIEW_REQUIRED")),
        evidence={"report": data},
    )


def run_hwpx_integrity_gate(
    path: str,
    *,
    allowed_names: tuple[str, ...] | list[str] = (),
    semantic_validator: Callable[[str], Any] = check_hwpx_semantics,
    acceptance_validator: Callable[..., Any] = run_hwpx_acceptance,
    render_validator: Callable[[str], Any] | None = None,
    fixed_cell_overflow: list[str] | tuple[str, ...] = (),
) -> IntegrityGateReport:
    """HWPX 구조·수용검사를 공통 계약으로 실행하고 severity를 집계한다.

    ``fixed_cell_overflow`` 는 XML 폭/높이 가드가 발견한 렌더링 위험 후보다.
    실제 한글 렌더링으로 확정하지 않으므로 HARD_FAIL이 아니라 REVIEW_REQUIRED로
    기록한다. 빈 목록이면 해당 validator를 생략해 기존 정상 출력 계약을 보존한다.
    """
    report = IntegrityGateReport(source=str(path))
    report.validators.append(
        _run_structural_validator("check_hwpx_semantics", semantic_validator, path)
    )
    report.validators.append(
        _run_structural_validator(
            "run_hwpx_acceptance",
            acceptance_validator,
            path,
            allowed_names=tuple(allowed_names),
        )
    )
    if fixed_cell_overflow:
        report.validators.append(
            ValidatorResult(
                source_validator="fixed_cell_height_guard",
                validator_status=EXECUTED,
                severity=REVIEW_REQUIRED,
                message="고정 셀 높이 초과 가능성이 있어 실제 렌더링 검토가 필요합니다.",
                defect_code="FIXED_CELL_RENDER_RISK",
                evidence={
                    "overflow_cells": [str(item) for item in fixed_cell_overflow],
                    "render_confirmed": False,
                    "reason": "XML 폭/높이 가드는 후보만 판정하며 glyph clipping을 확정하지 않음",
                },
            )
        )
    rendered = _run_render_validator(path, render_validator)
    if rendered is not None:
        report.validators.append(rendered)
    return report


__all__ = [
    "ERROR",
    "EXECUTED",
    "HARD_FAIL",
    "IntegrityGateReport",
    "PASS",
    "REVIEW_REQUIRED",
    "TIMEOUT",
    "UNAVAILABLE",
    "ValidatorResult",
    "WARNING",
    "run_hwpx_integrity_gate",
]
