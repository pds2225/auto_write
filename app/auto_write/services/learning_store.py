"""learning_store.py — auto_write 자가학습 레이어 순수 저장소(append-only JSONL).

이 모듈은 workspace/learning/ 아래에 실행 이력(runs.jsonl)·결함(defects.jsonl)·
selfdev 후보(selfdev_candidates.jsonl)를 append 로 누적하고, 필요할 때 읽어온다.
AI 호출 없음·순수 파일 I/O 만 한다(다른 서비스 모듈을 import 하지 않는다).

원칙
----
- 파일이 없으면 자동 생성한다(부모 폴더 mkdir 포함).
- 깨진 JSONL 줄은 예외로 죽지 않고 그 줄만 건너뛰고 stderr 에 경고만 남긴다.
- 모든 저장은 ``ensure_ascii=False`` (한글이 유니코드 이스케이프로 깨지지 않게).
- ``root`` 파라미터는 테스트 격리(tmp_path 주입)를 위해 모든 함수에 존재한다 —
  기본값만 ``LEARNING_ROOT``.

(§9 M8: section_playbooks / template_memory 는 1차에서 소비자가 없어 제외했다.
 실제로 그 값을 읽는 코드가 생기는 2·3차에 함께 추가한다.)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# app/auto_write/services/learning_store.py 기준: services→auto_write→app→<repo root>
LEARNING_ROOT = Path(__file__).resolve().parents[3] / "workspace" / "learning"

_RUNS_FILE = "runs.jsonl"
_DEFECTS_FILE = "defects.jsonl"
_SELFDEV_FILE = "selfdev_candidates.jsonl"


def _resolve_root(root: Path | None) -> Path:
    return Path(root) if root is not None else LEARNING_ROOT


def _append_jsonl(filename: str, record: dict[str, Any], root: Path | None) -> Path:
    r = _resolve_root(root)
    r.mkdir(parents=True, exist_ok=True)
    path = r / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def _load_jsonl(filename: str, root: Path | None) -> list[dict[str, Any]]:
    r = _resolve_root(root)
    path = r / filename
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                f"[경고] {path.name}:{lineno} 줄 JSON 파싱 실패 — 건너뜀 ({exc})",
                file=sys.stderr,
            )
            continue
        if isinstance(rec, dict):
            out.append(rec)
        else:
            print(f"[경고] {path.name}:{lineno} 줄이 객체가 아님 — 건너뜀", file=sys.stderr)
    return out


# --- append ------------------------------------------------------------------

def append_run(record: dict[str, Any], root: Path | None = None) -> Path:
    return _append_jsonl(_RUNS_FILE, record, root)


def append_defect(record: dict[str, Any], root: Path | None = None) -> Path:
    return _append_jsonl(_DEFECTS_FILE, record, root)


def append_selfdev_candidate(record: dict[str, Any], root: Path | None = None) -> Path:
    return _append_jsonl(_SELFDEV_FILE, record, root)


# --- load ----------------------------------------------------------------

def load_recent_runs(limit: int = 20, root: Path | None = None) -> list[dict[str, Any]]:
    """최신순(가장 최근 실행이 0번)으로 최대 limit 개의 run 레코드를 반환한다."""
    runs = _load_jsonl(_RUNS_FILE, root)
    if limit <= 0:
        return []
    return list(reversed(runs))[:limit]


def load_defects(
    recent_run_ids: list[str] | None = None, root: Path | None = None
) -> list[dict[str, Any]]:
    """defects.jsonl 전체(또는 recent_run_ids 에 속한 run_id 만) 반환."""
    defects = _load_jsonl(_DEFECTS_FILE, root)
    if recent_run_ids is None:
        return defects
    ids = set(recent_run_ids)
    return [d for d in defects if d.get("run_id") in ids]


def load_selfdev_candidates(root: Path | None = None) -> list[dict[str, Any]]:
    return _load_jsonl(_SELFDEV_FILE, root)


def load_defect_stats(last_n_runs: int = 5, root: Path | None = None) -> dict[str, dict[str, Any]]:
    """check_id → {count, runs:[...]} — 최근 last_n_runs 회 '실행' 범위에서 집계한다.

    (§9 M1) count/runs 는 defects.jsonl 의 '행 수'가 아니라 **서로 다른(distinct)
    run_id 의 수**다. 같은 실행 안에서 같은 check_id 가 여러 행으로 기록돼도
    반복(재발) 1회로만 센다 — 그렇지 않으면 한 번의 실행이 여러 결함 행을 남길 때
    반복 결함으로 오판(허위 selfdev 후보 승격)할 위험이 있다.
    """
    recent_runs = load_recent_runs(limit=last_n_runs, root=root)
    run_ids = [r.get("run_id") for r in recent_runs if r.get("run_id")]
    defects = load_defects(recent_run_ids=run_ids, root=root)

    stats: dict[str, dict[str, Any]] = {}
    for d in defects:
        check_id = d.get("check_id")
        run_id = d.get("run_id")
        if not check_id or not run_id:
            continue
        entry = stats.setdefault(check_id, {"count": 0, "runs": []})
        if run_id not in entry["runs"]:
            entry["runs"].append(run_id)
    for entry in stats.values():
        entry["count"] = len(entry["runs"])
    return stats
