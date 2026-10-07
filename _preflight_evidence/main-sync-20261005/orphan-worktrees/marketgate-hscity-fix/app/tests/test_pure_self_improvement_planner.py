"""test_pure_self_improvement_planner.py — 반복 결함 → selfdev 후보 승격 안전망.

self_improvement_planner 는 최근 실행 창에서 REPEAT_PROMOTE_N 회 이상 재발한
결함만 selfdev 후보로 등록한다(코드 자동수정은 하지 않음). learning_store 의
root 주입으로 tmp_path 에 완전 격리해 검증한다. 야간 안전망(2026-07-16).

여기서 고정하는 계약(§9 F1 — 날조0 하드 규칙 포함):
- kind=human 결함은 반복돼도 code_improvement 가 아니라 prompt_rule 후보만
  (requires_code_change=False, "날조 금지" 안내) — 코드가 값을 지어내게 유도 금지.
- auto/manual 결함 반복은 code_improvement(requires_code_change=True).
- 같은 (check_id, type) 후보는 candidate_id 해시로 1회만 등록(멱등).
"""

from __future__ import annotations

from auto_write.services.defect_classifier import REPEAT_PROMOTE_N
from auto_write.services.learning_store import (
    append_defect,
    append_run,
    load_selfdev_candidates,
)
from auto_write.services.self_improvement_planner import (
    _candidate_id,
    _priority,
    plan_candidates,
)
from auto_write.services.usage_acceptance import SEV_FAIL, SEV_WARN


def _seed_repeats(root, check_id: str, severity: str, n_runs: int) -> None:
    """check_id 결함이 n_runs 개의 서로 다른 실행에서 재발한 이력을 심는다."""
    for i in range(n_runs):
        rid = f"{check_id}-run{i}"
        append_run({"run_id": rid}, root=root)
        append_defect(
            {"run_id": rid, "check_id": check_id, "severity": severity}, root=root)


# --- 승격 규칙 --------------------------------------------------------------------

def test_auto_defect_repeats_promote_to_code_improvement(tmp_path):
    _seed_repeats(tmp_path, "self_inserted_blocks", SEV_FAIL, REPEAT_PROMOTE_N)
    got = plan_candidates(root=tmp_path)
    assert len(got) == 1
    cand = got[0]
    assert cand["type"] == "code_improvement"
    assert cand["requires_code_change"] is True
    assert cand["priority"] == "high"               # fail + 임계 이상 재발
    assert len(cand["evidence_runs"]) == REPEAT_PROMOTE_N


def test_human_defect_repeats_become_prompt_rule_only(tmp_path):
    # §9 F1: 사람 입력 결함([확인필요] 등)은 코드 수정 후보로 절대 승격 금지.
    _seed_repeats(tmp_path, "unresolved_markers", SEV_FAIL, REPEAT_PROMOTE_N + 1)
    got = plan_candidates(root=tmp_path)
    assert len(got) == 1
    cand = got[0]
    assert cand["type"] == "prompt_rule"
    assert cand["requires_code_change"] is False
    assert "날조 금지" in cand["suggested_action"]


def test_below_threshold_not_promoted(tmp_path):
    _seed_repeats(tmp_path, "self_inserted_blocks", SEV_FAIL, REPEAT_PROMOTE_N - 1)
    assert plan_candidates(root=tmp_path) == []
    assert load_selfdev_candidates(root=tmp_path) == []


def test_plan_is_idempotent_across_calls(tmp_path):
    _seed_repeats(tmp_path, "self_inserted_blocks", SEV_FAIL, REPEAT_PROMOTE_N)
    first = plan_candidates(root=tmp_path)
    second = plan_candidates(root=tmp_path)         # 같은 이력 재계획
    assert len(first) == 1 and second == []          # 새로 등록된 것만 반환
    assert len(load_selfdev_candidates(root=tmp_path)) == 1   # 파일에도 1건뿐


def test_empty_history_returns_empty(tmp_path):
    assert plan_candidates(root=tmp_path) == []


# --- 보조 헬퍼 --------------------------------------------------------------------

def test_candidate_id_is_deterministic_and_type_scoped():
    a1 = _candidate_id("marker", "code_improvement")
    a2 = _candidate_id("marker", "code_improvement")
    b = _candidate_id("marker", "prompt_rule")
    assert a1 == a2 and a1 != b and len(a1) == 12


def test_priority_matrix():
    assert _priority(SEV_FAIL, REPEAT_PROMOTE_N) == "high"
    assert _priority(SEV_WARN, 2) == "medium"
    assert _priority(SEV_WARN, 1) == "low"
    # fail 이지만 임계 미만이면 high 도 medium 도 아님(보수적 low).
    assert _priority(SEV_FAIL, REPEAT_PROMOTE_N - 1) == "low"
