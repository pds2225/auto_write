"""learning_store 순수 저장소 테스트.

append→load 왕복 / 파일 없음 자동생성(폴더까지) / 깨진 JSONL 줄 skip+경고 /
root 격리(tmp_path) / §9 M1 — load_defect_stats 는 distinct run_id 기준 집계.
"""

from __future__ import annotations

import json
from pathlib import Path

from auto_write.services import learning_store as store


def test_append_and_load_roundtrip(tmp_path: Path) -> None:
    rec = {"run_id": "r1", "check_id": "unresolved_markers", "note": "테스트"}
    path = store.append_run(rec, root=tmp_path)
    assert path.exists()
    runs = store.load_recent_runs(limit=10, root=tmp_path)
    assert runs == [rec]


def test_load_missing_file_returns_empty_no_crash(tmp_path: Path) -> None:
    runs = store.load_recent_runs(root=tmp_path / "no_such_dir")
    assert runs == []
    defects = store.load_defects(root=tmp_path / "no_such_dir")
    assert defects == []


def test_append_autocreates_missing_parent_dirs(tmp_path: Path) -> None:
    root = tmp_path / "a" / "b" / "c"
    assert not root.exists()
    store.append_defect({"run_id": "r1", "check_id": "x"}, root=root)
    assert (root / "defects.jsonl").exists()


def test_broken_jsonl_line_is_skipped_with_stderr_warning(tmp_path: Path, capsys) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "runs.jsonl"
    path.write_text(
        json.dumps({"run_id": "good1"}, ensure_ascii=False) + "\n"
        + "{이건 깨진 json 줄}\n"
        + json.dumps({"run_id": "good2"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    runs = store.load_recent_runs(limit=10, root=tmp_path)

    ids = {r["run_id"] for r in runs}
    assert ids == {"good1", "good2"}
    captured = capsys.readouterr()
    assert "경고" in captured.err


def test_root_isolation_between_paths(tmp_path_factory) -> None:
    root_a = tmp_path_factory.mktemp("a")
    root_b = tmp_path_factory.mktemp("b")
    store.append_run({"run_id": "only_in_a"}, root=root_a)
    assert store.load_recent_runs(root=root_a) != []
    assert store.load_recent_runs(root=root_b) == []


def test_load_recent_runs_returns_most_recent_first(tmp_path: Path) -> None:
    for i in range(3):
        store.append_run({"run_id": f"r{i}"}, root=tmp_path)
    runs = store.load_recent_runs(limit=10, root=tmp_path)
    assert [r["run_id"] for r in runs] == ["r2", "r1", "r0"]


def test_load_defect_stats_dedups_rows_within_same_run(tmp_path: Path) -> None:
    """§9 M1: 같은 실행(run_id) 안에서 같은 check_id 가 3행 기록돼도 반복 1회로만 센다."""
    store.append_run({"run_id": "run_a"}, root=tmp_path)
    for _ in range(3):
        store.append_defect({"run_id": "run_a", "check_id": "unresolved_markers"}, root=tmp_path)

    stats = store.load_defect_stats(last_n_runs=5, root=tmp_path)

    assert stats["unresolved_markers"]["count"] == 1
    assert stats["unresolved_markers"]["runs"] == ["run_a"]


def test_load_defect_stats_counts_distinct_runs(tmp_path: Path) -> None:
    for run_id in ("run_a", "run_b", "run_c"):
        store.append_run({"run_id": run_id}, root=tmp_path)
        store.append_defect({"run_id": run_id, "check_id": "unresolved_markers"}, root=tmp_path)

    stats = store.load_defect_stats(last_n_runs=5, root=tmp_path)

    assert stats["unresolved_markers"]["count"] == 3
    assert set(stats["unresolved_markers"]["runs"]) == {"run_a", "run_b", "run_c"}
