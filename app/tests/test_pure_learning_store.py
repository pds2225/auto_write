"""test_pure_learning_store.py — 자가학습 append-only 저장소(JSONL) 안전망.

learning_store 는 실행 이력·결함·selfdev 후보를 JSONL 로 누적한다. 모든 함수가
``root`` 주입을 지원해 tmp_path 로 완전 격리된다(실 workspace/learning 불건드림).
야간 안전망(2026-07-16).

여기서 고정하는 계약:
- ensure_ascii=False — 한글이 유니코드 이스케이프로 깨지지 않고 원문 저장.
- 깨진 JSONL 줄·객체 아닌 줄은 예외로 죽지 않고 그 줄만 건너뛴다(경고만).
- load_recent_runs 는 최신순(마지막 append 가 0번), limit<=0 이면 빈 목록.
- load_defect_stats 의 count 는 행 수가 아니라 **distinct run_id 수**(§9 M1) —
  한 실행이 같은 check_id 결함을 여러 행 남겨도 재발 1회로만 센다.
"""

from __future__ import annotations

import json

from auto_write.services.learning_store import (
    append_defect,
    append_run,
    append_selfdev_candidate,
    load_defect_stats,
    load_defects,
    load_recent_runs,
    load_selfdev_candidates,
)


def test_append_and_load_roundtrip_keeps_hangul_raw(tmp_path):
    path = append_run({"run_id": "r1", "메모": "한글 그대로"}, root=tmp_path)
    assert path.parent == tmp_path                    # root 주입 — 격리 확인
    raw = path.read_text(encoding="utf-8")
    assert "한글 그대로" in raw                        # ensure_ascii=False
    assert "\\u" not in raw
    assert load_recent_runs(root=tmp_path) == [{"run_id": "r1", "메모": "한글 그대로"}]


def test_load_skips_broken_and_non_object_lines(tmp_path, capsys):
    append_run({"run_id": "r1"}, root=tmp_path)
    runs_file = tmp_path / "runs.jsonl"
    with runs_file.open("a", encoding="utf-8") as f:
        f.write("{깨진 json\n")                        # 파싱 불가 줄
        f.write('["객체가", "아님"]\n')                # dict 아님
    append_run({"run_id": "r2"}, root=tmp_path)

    runs = load_recent_runs(root=tmp_path)
    assert [r["run_id"] for r in runs] == ["r2", "r1"]  # 나쁜 줄만 건너뜀·순서 최신순
    err = capsys.readouterr().err
    assert "파싱 실패" in err and "객체가 아님" in err


def test_load_recent_runs_limit_and_zero(tmp_path):
    for i in range(5):
        append_run({"run_id": f"r{i}"}, root=tmp_path)
    assert [r["run_id"] for r in load_recent_runs(limit=2, root=tmp_path)] == ["r4", "r3"]
    assert load_recent_runs(limit=0, root=tmp_path) == []
    assert load_recent_runs(root=tmp_path / "없는폴더") == []   # 파일 없음 → 빈 목록


def test_load_defects_filters_by_run_ids(tmp_path):
    append_defect({"run_id": "r1", "check_id": "a"}, root=tmp_path)
    append_defect({"run_id": "r2", "check_id": "b"}, root=tmp_path)
    assert len(load_defects(root=tmp_path)) == 2                       # 필터 없음 → 전체
    only_r2 = load_defects(recent_run_ids=["r2"], root=tmp_path)
    assert [d["check_id"] for d in only_r2] == ["b"]
    assert load_defects(recent_run_ids=[], root=tmp_path) == []


def test_defect_stats_counts_distinct_runs_not_rows(tmp_path):
    # r1 에서 같은 check_id 결함이 3행 — 재발 1회로만 센다(§9 M1).
    append_run({"run_id": "r1"}, root=tmp_path)
    append_run({"run_id": "r2"}, root=tmp_path)
    for _ in range(3):
        append_defect({"run_id": "r1", "check_id": "marker"}, root=tmp_path)
    append_defect({"run_id": "r2", "check_id": "marker"}, root=tmp_path)
    append_defect({"run_id": "r2", "check_id": ""}, root=tmp_path)     # 무효 행 무시

    stats = load_defect_stats(root=tmp_path)
    assert stats["marker"]["count"] == 2                # 행 5 가 아니라 run 2
    assert stats["marker"]["runs"] == ["r1", "r2"]


def test_defect_stats_window_excludes_old_runs(tmp_path):
    # 최근 last_n_runs 회 밖의 옛 실행 결함은 집계하지 않는다.
    for i in range(4):
        append_run({"run_id": f"r{i}"}, root=tmp_path)
    append_defect({"run_id": "r0", "check_id": "old_only"}, root=tmp_path)
    append_defect({"run_id": "r3", "check_id": "recent"}, root=tmp_path)

    stats = load_defect_stats(last_n_runs=2, root=tmp_path)            # r3, r2 만
    assert "old_only" not in stats
    assert stats["recent"]["count"] == 1


def test_selfdev_candidates_roundtrip(tmp_path):
    append_selfdev_candidate({"candidate_id": "c1", "check_id": "x"}, root=tmp_path)
    got = load_selfdev_candidates(root=tmp_path)
    assert got == [{"candidate_id": "c1", "check_id": "x"}]
    # 파일이 진짜 JSONL(줄당 1 JSON)인지도 고정.
    lines = (tmp_path / "selfdev_candidates.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["candidate_id"] == "c1"
