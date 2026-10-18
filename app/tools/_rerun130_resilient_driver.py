# -*- coding: utf-8 -*-
"""_rerun130_resilient_driver — rerun_l3_batch 를 파일 1개씩 격리 프로세스+타임아웃으로 돌린다.

일부 환경에서 Hangul COM 자동화(real_fill)가 간헐적으로 멈추는 현상이 있다(추정 원인: 이미
떠 있던 다른 Hwp.exe 인스턴스와의 COM 재사용 경합). 이 스크립트는 rerun_l3_batch.measure() 를
파일마다 새 파이썬 프로세스로 실행하고 하드 타임아웃을 걸어, 한 파일이 멈춰도 전체 배치가
막히지 않게 한다. 멈추면 그 측정만 TIMEOUT 으로 기록하고(새로 띄운 Hwp.exe 만 정리— 이미
떠 있던 것은 건드리지 않는다) 다음 파일로 넘어간다(최대 2회 재시도).

이 파일은 측정 보조 스크립트이며 엔진 코드(app/core, app/auto_write/services)는 건드리지 않는다.

    python app/tools/_rerun130_resilient_driver.py <양식폴더> --out data/rerun130_p1 \
        [--extra-dir <변환HWPX폴더>]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rerun_l3_batch import (  # noqa: E402
    FIELDS,
    list_targets,
    write_outputs,
)

TIMEOUT_SECS = 220
MAX_ATTEMPTS = 2

_WORKER = r"""
import sys, json
sys.path.insert(0, {tools_dir!r})
sys.path.insert(0, {app_dir!r})
from pathlib import Path
from rerun_l3_batch import measure, FAKE_IDENTITY
import tempfile
p = Path({path!r})
with tempfile.TemporaryDirectory(prefix="rerun130_") as td:
    row = measure(p, Path(td), FAKE_IDENTITY)
print("===ROW_JSON_START===")
print(json.dumps(row, ensure_ascii=False, default=str))
print("===ROW_JSON_END===")
"""


def _hwp_pids() -> set[str]:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Hwp.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return set()
    pids = set()
    for line in out.splitlines():
        parts = [c.strip('"') for c in line.strip().split('","')]
        if len(parts) >= 2 and parts[0].lower().startswith("hwp"):
            pids.add(parts[1].strip('"'))
    return pids


def _kill_new_hwp(baseline: set[str]) -> None:
    for pid in _hwp_pids() - baseline:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)


def _run_one(path: Path, tools_dir: str, app_dir: str, baseline_hwp: set[str]) -> dict | None:
    script = _WORKER.format(tools_dir=tools_dir, app_dir=app_dir, path=str(path))
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, encoding="utf-8",
            timeout=TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired:
        # Hangul COM 자동화가 멈춘 상태 — 이 측정이 새로 띄운 Hwp.exe 만 정리한다
        # (세션 시작 시점에 이미 떠 있던 것은 내가 띄운 게 아니므로 건드리지 않는다).
        _kill_new_hwp(baseline_hwp)
        return None
    out = proc.stdout
    if "===ROW_JSON_START===" not in out:
        return {
            "file": str(path), "name": path.name, "kind": "양식", "passed": 0,
            "crash": f"WORKER_FAIL rc={proc.returncode} stderr={proc.stderr[-300:]}",
            "fail_reason": "측정 프로세스 비정상 종료",
            **{k: "" for k in FIELDS if k not in ("file", "name", "kind", "passed", "crash", "fail_reason")},
        }
    blob = out.split("===ROW_JSON_START===")[1].split("===ROW_JSON_END===")[0].strip()
    return json.loads(blob)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="rerun_l3_batch 파일 단위 격리 실행(타임아웃+재시도)")
    ap.add_argument("folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--extra-dir", action="append", default=[])
    a = ap.parse_args(argv)
    folder = Path(a.folder)
    out_dir = Path(a.out)

    tools_dir = str(Path(__file__).resolve().parent)
    app_dir = str(Path(__file__).resolve().parent.parent)
    targets, skipped = list_targets([folder, *map(Path, a.extra_dir)])
    out_dir.mkdir(parents=True, exist_ok=True)
    baseline_hwp = _hwp_pids()
    print(f"baseline Hwp.exe pids (pre-existing, never killed): {sorted(baseline_hwp)}", flush=True)
    rows: list[dict] = []
    with open(out_dir / "progress.jsonl", "w", encoding="utf-8") as prog:
        for i, p in enumerate(targets, 1):
            row = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                t0 = time.time()
                row = _run_one(p, tools_dir, app_dir, baseline_hwp)
                dt = round(time.time() - t0, 1)
                if row is not None:
                    break
                print(f"[{i}/{len(targets)}] TIMEOUT attempt {attempt}/{MAX_ATTEMPTS} "
                      f"after {dt}s: {p.name}", flush=True)
            if row is None:
                row = {
                    "file": str(p), "name": p.name, "kind": "양식", "passed": 0,
                    "crash": f"TIMEOUT after {MAX_ATTEMPTS} attempts (>{TIMEOUT_SECS}s each)",
                    "fail_reason": "측정 타임아웃(Hangul 자동화 응답 없음)",
                    **{k: "" for k in FIELDS if k not in ("file", "name", "kind", "passed", "crash", "fail_reason")},
                }
            rows.append(row)
            prog.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            prog.flush()
            print(f"[{i}/{len(targets)}] {row.get('kind')} P {row.get('profile_fill')}/{row.get('profile_app')} "
                  f"{'CRASH ' if row.get('crash') else ''}{p.name}", flush=True)
    s = write_outputs(out_dir, rows, skipped, {"commit": "", "folder": str(folder), "extra_dirs": a.extra_dir})
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
