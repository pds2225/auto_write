"""defect_classifier.py — 수용검사 결함 1건을 자가학습 6분류(category)로 분류한다.

분류 근거는 ``acceptance_remediation.remedy_for``(kind: auto/human/manual) 를
단일 출처로 재사용한다 — 이 모듈에 중복 매핑표를 새로 두지 않는다.

§9 F1 (날조0 최우선, 하드 규칙)
------------------------------
``human_input`` (kind=human: 사람이 실제 값·선택을 입력해야만 하는 결함)은
반복해도 ``auto_fix`` 로도 ``code_improvement`` 로도 **절대 승격하지 않는다**.
승격하면 다음 실행 파이프라인(/auto-write-selfdev)이 "코드가 알아서 채워야
한다"는 압박을 받아 없는 값을 지어내는 함정이 된다. 재발한 human_input 은
category=human_input 을 유지하며, 재발 자체는 self_improvement_planner 가
"상류(입력 단계)를 더 일찍 물어보게 하라"는 prompt_rule 후보로만 승격한다.

1차(Phase 1) 범위: ``classify_check`` 만 구현한다. 섹션별 평가 취약점
분류(classify_eval_weakness)·양식 매핑 잔차 분류(classify_field_residual)는
호출자·데이터 소스가 아직 없어 2·3차로 미룬다(§9 F5) — 상수만 예약해 둔다.
"""

from __future__ import annotations

from typing import Any

from .acceptance_remediation import DOC_TOKEN, KIND_AUTO, KIND_HUMAN, KIND_MANUAL, Remedy, remedy_for
from .usage_acceptance import SEV_FAIL, SEV_WARN

# --- 자가학습 6분류 ------------------------------------------------------
CAT_AUTO_FIX = "auto_fix"
CAT_HUMAN_INPUT = "human_input"
CAT_MANUAL_REVIEW = "manual_review"
CAT_PROMPT_RULE = "prompt_rule"          # 2차 전용(§9 F5) — 1차는 예약만, 함수 미구현
CAT_FIELD_MAPPING = "field_mapping"      # 3차 전용(§9 F5) — 1차는 예약만, 함수 미구현
CAT_CODE_IMPROVEMENT = "code_improvement"

# §9 M7: 승격 임계 상수를 이 모듈에 단일 정의하고, self_improvement_planner 가 import 해 쓴다.
REPEAT_PROMOTE_N = 3   # 최근 실행 창(WINDOW_N) 중 이 횟수 이상 재발하면 승격 검토
WINDOW_N = 5           # "최근 N 회 실행" 창 크기


def _as_check_dict(check: Any) -> dict[str, Any]:
    """CheckResult(.as_dict 보유) 또는 이미 dict 인 값을 균일한 dict 로 정규화한다."""
    as_dict = getattr(check, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    return dict(check)


def classify_check(
    check: Any, *, repeat_count: int = 0, remedy: Remedy | None = None, doc_name: str = "",
) -> dict[str, Any]:
    """수용검사 결과 1건(usage_acceptance.CheckResult 또는 동일 shape 의 dict)을 분류한다.

    Args:
        check: CheckResult 객체 또는 ``{check_id, label, severity, defects, samples, ...}``.
        repeat_count: 최근 실행 창에서 이 check_id 가 재발한 '서로 다른 실행' 횟수
            (learning_store.load_defect_stats 의 count — distinct run_id 기준, §9 M1).
        remedy: 이미 계산된 Remedy 가 있으면 재사용한다(§9 M6, remedy_for 중복 계산 회피).
            없으면 이 함수가 직접 ``remedy_for(check_id)`` 로 조회한다.
        doc_name: 자동 명령(command)의 ``{doc}`` 자리표시를 실제 문서 경로로 치환할 때
            쓴다(acceptance_remediation.build_remediation 과 동일 관례). 비우면
            치환하지 않고 원본 템플릿 그대로 반환한다(하위 호환).

    Returns:
        {check_id, label, severity, defects, samples, category, next_action, command}
    """
    data = _as_check_dict(check)
    check_id = data.get("check_id", "")
    rem = remedy or remedy_for(check_id)

    if rem.kind == KIND_AUTO:
        category = CAT_AUTO_FIX
    elif rem.kind == KIND_HUMAN:
        category = CAT_HUMAN_INPUT
    else:
        category = CAT_MANUAL_REVIEW

    # §9 F1: human_input 은 아래 승격 조건에서 영구 제외된다(kind==human 은
    # _PROMOTABLE_KINDS 에 없고, severity 조건과 무관하게 category 는 그대로 유지됨).
    severity = data.get("severity", "")
    promotable = rem.kind == KIND_MANUAL or (rem.kind == KIND_AUTO and severity == SEV_WARN)
    if repeat_count >= REPEAT_PROMOTE_N and promotable:
        category = CAT_CODE_IMPROVEMENT

    command = rem.command.replace(DOC_TOKEN, doc_name) if (rem.command and doc_name) else rem.command

    return {
        "check_id": check_id,
        "label": data.get("label", ""),
        "severity": severity,
        "defects": data.get("defects", 0),
        "samples": list(data.get("samples") or [])[:5],
        "category": category,
        "next_action": rem.action,
        "command": command,
    }
