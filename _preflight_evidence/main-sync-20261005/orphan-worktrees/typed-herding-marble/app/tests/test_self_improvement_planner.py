"""self_improvement_planner selfdev 후보 생성 테스트.

5회 중 3회 반복(distinct run_id)→후보 생성 / 2회→미생성 / 중복 candidate_id skip /
§9 F1 human→prompt_rule(requires_code_change=False, code_improvement 아님) /
§9 M1 한 실행 3행→후보 아님.
"""

from __future__ import annotations

from pathlib import Path

from auto_write.services.defect_classifier import (
    CAT_CODE_IMPROVEMENT,
    CAT_PROMPT_RULE,
    REPEAT_PROMOTE_N,
)
from auto_write.services.learning_store import append_defect, append_run, load_selfdev_candidates
from auto_write.services.self_improvement_planner import plan_candidates


def _seed(root: Path, check_id: str, severity: str, n_runs: int, rows_per_run: int = 1) -> None:
    for i in range(n_runs):
        run_id = f"run_{i}"
        append_run({"run_id": run_id}, root=root)
        for _ in range(rows_per_run):
            append_defect({"run_id": run_id, "check_id": check_id, "severity": severity}, root=root)


def test_repeat_3_of_5_distinct_runs_creates_candidate(tmp_path: Path) -> None:
    _seed(tmp_path, "masking_violation", "fail", n_runs=REPEAT_PROMOTE_N)

    candidates = plan_candidates(root=tmp_path, last_n_runs=5)

    assert len(candidates) == 1
    assert candidates[0]["check_id"] == "masking_violation"
    assert candidates[0]["type"] == CAT_CODE_IMPROVEMENT
    assert candidates[0]["requires_code_change"] is True
    assert len(load_selfdev_candidates(root=tmp_path)) == 1


def test_repeat_2_of_5_does_not_create_candidate(tmp_path: Path) -> None:
    _seed(tmp_path, "masking_violation", "fail", n_runs=REPEAT_PROMOTE_N - 1)

    candidates = plan_candidates(root=tmp_path, last_n_runs=5)

    assert candidates == []
    assert load_selfdev_candidates(root=tmp_path) == []


def test_duplicate_candidate_not_reregistered_on_second_call(tmp_path: Path) -> None:
    _seed(tmp_path, "masking_violation", "fail", n_runs=REPEAT_PROMOTE_N)

    first = plan_candidates(root=tmp_path, last_n_runs=5)
    second = plan_candidates(root=tmp_path, last_n_runs=5)

    assert len(first) == 1
    assert second == []  # 이미 등록된 candidate_id 는 다시 반환·저장하지 않는다
    assert len(load_selfdev_candidates(root=tmp_path)) == 1


def test_human_check_becomes_prompt_rule_never_code_improvement(tmp_path: Path) -> None:
    """§9 F1: human_input(unresolved_markers, KIND_HUMAN)이 반복돼도 code_improvement 후보가 아니다."""
    _seed(tmp_path, "unresolved_markers", "fail", n_runs=REPEAT_PROMOTE_N)

    candidates = plan_candidates(root=tmp_path, last_n_runs=5)

    assert len(candidates) == 1
    c = candidates[0]
    assert c["type"] == CAT_PROMPT_RULE
    assert c["type"] != CAT_CODE_IMPROVEMENT
    assert c["requires_code_change"] is False


def test_one_run_three_rows_is_not_a_candidate(tmp_path: Path) -> None:
    """§9 M1: 같은 실행(run_id) 안 3행은 재발 1회로만 세어 승격 임계에 못 미친다."""
    _seed(tmp_path, "masking_violation", "fail", n_runs=1, rows_per_run=3)

    candidates = plan_candidates(root=tmp_path, last_n_runs=5)

    assert candidates == []


def test_priority_high_for_fail_severity_repeated(tmp_path: Path) -> None:
    _seed(tmp_path, "masking_violation", "fail", n_runs=REPEAT_PROMOTE_N)
    candidates = plan_candidates(root=tmp_path, last_n_runs=5)
    assert candidates[0]["priority"] == "high"


def test_no_defects_returns_empty_list(tmp_path: Path) -> None:
    assert plan_candidates(root=tmp_path, last_n_runs=5) == []
