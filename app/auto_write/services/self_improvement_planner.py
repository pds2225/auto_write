"""self_improvement_planner.py — 반복 결함을 selfdev 후보로 등록한다(코드 자동수정 없음).

이 모듈은 **코드를 고치지 않는다** — 최근 실행 창(WINDOW_N)에서 REPEAT_PROMOTE_N 회
이상 재발한 결함을 골라 ``selfdev_candidates.jsonl`` 에 후보로 남기는 것까지만 한다.
실제 코드 수정은 사람이 검토해 ``/auto-write-selfdev`` 로 진행한다(§5 안전 원칙 3).

§9 F1 (날조0 최우선): kind=human(사람이 직접 입력해야 하는 결함, 예: [확인필요]
마커·미체크 선택란)이 반복돼도 ``code_improvement``/``requires_code_change=True``
후보로 만들지 않는다. 대신 "상류(입력 단계)를 더 일찍 물어보게 하라"는
``prompt_rule`` 후보(``requires_code_change=False``)만 만든다 — 없는 값을 코드가
지어내도록 유도하는 함정을 원천 차단한다.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from .acceptance_remediation import KIND_HUMAN, remedy_for
from .defect_classifier import (
    CAT_CODE_IMPROVEMENT,
    CAT_PROMPT_RULE,
    REPEAT_PROMOTE_N,
    WINDOW_N,
)
from .learning_store import (
    append_selfdev_candidate,
    load_defect_stats,
    load_defects,
    load_selfdev_candidates,
)
from .usage_acceptance import SEV_FAIL


def _candidate_id(check_id: str, ctype: str) -> str:
    """check_id+type 해시 — 같은 결함·같은 후보 유형은 항상 같은 id 를 낸다(중복 방지)."""
    return hashlib.sha1(f"{check_id}:{ctype}".encode("utf-8")).hexdigest()[:12]


def _priority(severity: str, repeat: int) -> str:
    """priority: fail·REPEAT_PROMOTE_N 회↑=high / warn·2회↑=medium / 그 외=low."""
    if severity == SEV_FAIL and repeat >= REPEAT_PROMOTE_N:
        return "high"
    if severity != SEV_FAIL and repeat >= 2:
        return "medium"
    return "low"


def plan_candidates(root: Path | None = None, *, last_n_runs: int = WINDOW_N) -> list[dict[str, Any]]:
    """최근 last_n_runs 회 실행의 결함 통계에서 반복 결함을 selfdev 후보로 승격한다.

    - 같은 check_id 가 최근 last_n_runs 회(distinct run_id, §9 M1) 중
      REPEAT_PROMOTE_N 회 이상 → kind=human 이면 prompt_rule 후보,
      그 외(auto/manual)면 code_improvement 후보(§9 F1).
    - 중복 candidate_id(check_id+type 해시)는 이미 저장돼 있으면 다시 등록하지 않는다.
    - 반환값은 이번 호출에서 **새로** 등록된 후보만 담는다(이미 등록된 것은 제외).
    """
    stats = load_defect_stats(last_n_runs=last_n_runs, root=root)
    if not stats:
        return []

    run_ids: list[str] = []
    for info in stats.values():
        run_ids.extend(info.get("runs", []))
    defects = load_defects(recent_run_ids=list(dict.fromkeys(run_ids)), root=root) if run_ids else []
    severity_by_check: dict[str, str] = {}
    for d in defects:
        cid = d.get("check_id")
        if cid and cid not in severity_by_check:
            severity_by_check[cid] = d.get("severity", "")

    existing_ids = {c.get("candidate_id") for c in load_selfdev_candidates(root=root)}
    new_candidates: list[dict[str, Any]] = []

    for check_id, info in stats.items():
        repeat = info.get("count", 0)
        if repeat < REPEAT_PROMOTE_N:
            continue

        rem = remedy_for(check_id)
        severity = severity_by_check.get(check_id, "")
        is_human = rem.kind == KIND_HUMAN

        if is_human:
            ctype = CAT_PROMPT_RULE
            requires_code_change = False
            reason = f"human_input 결함 반복(최근 {last_n_runs}회 중 {repeat}회) — 코드 자동수정 대상 아님"
            suggested_action = (
                f"'{check_id}' 값을 더 일찍(입력/수집 단계)에서 사람에게 물어보도록 상류를 "
                "보완하세요. 이 값을 코드가 자동으로 채우면 안 됩니다(날조 금지)."
            )
        else:
            ctype = CAT_CODE_IMPROVEMENT
            requires_code_change = True
            reason = f"{rem.kind} 결함 반복(최근 {last_n_runs}회 중 {repeat}회) — 자동화 보강 검토 대상"
            suggested_action = f"'{check_id}' 반복 결함 — {rem.action}"

        candidate_id = _candidate_id(check_id, ctype)
        if candidate_id in existing_ids:
            continue

        candidate = {
            "candidate_id": candidate_id,
            "check_id": check_id,
            "type": ctype,
            "priority": _priority(severity, repeat),
            "reason": reason,
            "evidence_runs": list(info.get("runs", [])),
            "suggested_action": suggested_action,
            "requires_code_change": requires_code_change,
        }
        try:
            append_selfdev_candidate(candidate, root=root)
        except OSError as exc:
            print(
                f"[경고] selfdev 후보 저장 실패({check_id}): {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue
        existing_ids.add(candidate_id)
        new_candidates.append(candidate)

    return new_candidates
