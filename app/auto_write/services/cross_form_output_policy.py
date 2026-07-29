"""cross_form_output_policy — 출력 형식·엔진 조합 검증(승인 없는 DOCX-only 우회 방지).

에이전트/CLI가 파이프라인을 바꿀 때 ``--confirm-output-plan`` 으로 사용자(또는 호출자)가
명시적으로 선택했음을 증명해야 한다. RHWP-only ≠ DOCX-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import AbstractSet


class OutputFormat(str, Enum):
    HWPX = "hwpx"
    HWP = "hwp"
    DOCX = "docx"


class FillEngine(str, Enum):
    """엔진 선택 — 암묵적 기본값 없음."""

    RHWP_HWPX = "rhwp-hwpx-fill"       # fill_hwpx, COM 없음
    COM_HWPX = "com-hwpx-fill"         # fill_hwp_via_hwpx (COM 변환 + hwpx_fill)
    DOCX_CROSSFORM = "docx-crossform"  # cross_form_fill → DOCX만


class OutputPolicyError(ValueError):
    """출력 계획이 정책에 어긋날 때."""


@dataclass(frozen=True)
class OutputPlan:
    outputs: frozenset[OutputFormat]
    engine: FillEngine
    user_confirmed: bool

    @classmethod
    def parse(
        cls,
        *,
        output_names: list[str],
        engine_name: str,
        user_confirmed: bool,
    ) -> OutputPlan:
        try:
            outputs = frozenset(OutputFormat(x.lower()) for x in output_names)
        except ValueError as exc:
            raise OutputPolicyError(
                f"알 수 없는 출력 형식: {output_names}. 허용: hwpx, hwp, docx"
            ) from exc
        if not outputs:
            raise OutputPolicyError("최소 1개 --output (hwpx|hwp|docx) 가 필요합니다.")
        try:
            engine = FillEngine(engine_name.lower())
        except ValueError as exc:
            raise OutputPolicyError(
                f"알 수 없는 엔진: {engine_name!r}. "
                f"허용: {', '.join(e.value for e in FillEngine)}"
            ) from exc
        return cls(outputs=outputs, engine=engine, user_confirmed=user_confirmed)

    def as_dict(self) -> dict:
        return {
            "outputs": sorted(o.value for o in self.outputs),
            "engine": self.engine.value,
            "user_confirmed": self.user_confirmed,
        }


def validate_output_plan(plan: OutputPlan) -> None:
    """승인 없는 우회·축소·대체를 코드로 차단한다."""
    if not plan.user_confirmed:
        raise OutputPolicyError(
            "출력 형식·엔진 변경은 --confirm-output-plan 플래그가 필요합니다. "
            "승인 없이 DOCX-only·엔진 축소를 실행할 수 없습니다."
        )

    o: AbstractSet[OutputFormat] = plan.outputs
    e = plan.engine

    if e is FillEngine.RHWP_HWPX:
        if OutputFormat.HWPX not in o:
            raise OutputPolicyError(
                "엔진 rhwp-hwpx-fill 은 --output hwpx 가 필수입니다. "
                "DOCX-only 우회는 금지됩니다."
            )
        if OutputFormat.HWP in o:
            raise OutputPolicyError(
                "rhwp-hwpx-fill 은 COM 없이 .hwp 를 만들 수 없습니다. "
                "--output hwp 를 빼거나 --engine com-hwpx-fill 을 선택하세요."
            )

    if e is FillEngine.COM_HWPX:
        if OutputFormat.HWPX not in o and OutputFormat.HWP not in o:
            raise OutputPolicyError(
                "com-hwpx-fill 은 --output hwpx 또는 hwp 가 필요합니다."
            )

    if e is FillEngine.DOCX_CROSSFORM:
        if OutputFormat.DOCX not in o:
            raise OutputPolicyError("docx-crossform 은 --output docx 가 필수입니다.")
        if OutputFormat.HWPX in o or OutputFormat.HWP in o:
            raise OutputPolicyError(
                "docx-crossform 은 .docx 만 출력합니다. "
                "hwpx/hwp 가 필요하면 rhwp-hwpx-fill 또는 com-hwpx-fill 을 선택하세요."
            )

    # RHWP 라벨만 달고 DOCX만 출력하는 오해 방지
    if e is FillEngine.RHWP_HWPX and OutputFormat.DOCX in o and OutputFormat.HWPX not in o:
        raise OutputPolicyError(
            "'RHWP' 엔진은 hwpx_fill 경로입니다. DOCX만 원하면 --engine docx-crossform 을 "
            "명시적으로 선택하세요."
        )
