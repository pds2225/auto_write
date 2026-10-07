r"""quality_ratchet CLI — 품질 기준선(ratchet) 갱신 + 시계열(trend) 누적.

mail 레포 accuracy_baseline.py 이식(auto_write 판). AI 키 없이 결정론 동작:
  1) 골든 문서(results/golden/*.docx)를 doc_quality_score 로 채점해
     3축(formatting/placement/image) 집계 — 핵심목적(위치·서식·이미지) 지표.
  2) pytest(tests/) 를 돌려 passed/failed 를 회귀검증 축으로 기록.
  3) baseline_metrics.json ratchet 판정 — 테스트 실패·passed 감소·
     (동일 골든셋) avg_total 하락 시 실패(exit 2). 좋아지면 기준선 전진.
  4) trend.csv 에 1행 append(시계열 — "계속 좋아지는 중" 증명).

산출물 (D:\auto_write\.omc\quality\):
  baseline_metrics.json   ratchet 기준선
  trend.csv               run,n_docs,avg_total,formatting,placement,image,tests
  runs/<라벨>/summary.json 실행별 상세(문서별 점수 포함)

실행 (PowerShell, D:\auto_write 에서 — 테스트는 반드시 py -3.11):
  py -3.11 app\quality_ratchet.py                     # 골든 채점 + pytest + ratchet
  py -3.11 app\quality_ratchet.py --skip-tests        # 문서 채점만
  py -3.11 app\quality_ratchet.py --golden-dir C:\경로  # 골든셋 지정
  py -3.11 app\quality_ratchet.py --seed              # 기준선 강제 재시딩
종료코드: 0 통과 / 2 게이트 위반(테스트 실패·passed 감소·점수 하락).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from auto_write.services.quality_ratchet import (  # noqa: E402
    TREND_HEADER, aggregate_dimensions, build_summary, build_trend_row, gate,
)

BASE_DIR = _APP_DIR.parent
QUALITY_DIR = BASE_DIR / ".omc" / "quality"
BASELINE = QUALITY_DIR / "baseline_metrics.json"
TREND = QUALITY_DIR / "trend.csv"
RUNS = QUALITY_DIR / "runs"
DEFAULT_GOLDEN = BASE_DIR / "results" / "golden"

_PYTEST_PASSED_RE = re.compile(r"(\d+) passed")
_PYTEST_FAILED_RE = re.compile(r"(\d+) failed")


def _fix_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass


def measure_docx(path: Path) -> dict[str, Any]:
    """DOCX 1건을 결정론 경로(AI 미호출)로 채점해 3축 집계까지 반환."""
    from docx import Document

    from auto_write.services.doc_quality_score import score_document
    from auto_write.services.document_type_classifier import classify_docx
    from auto_write.services.infographic_suggest import suggest_images_ai

    doc_type = classify_docx(str(path))          # 규칙 기반(AI 없음 → 규칙 유지)
    doc = Document(str(path))
    info = suggest_images_ai(doc, openai_service=None)  # 키워드 폴백(결정론)
    score = score_document(
        doc,
        doc_type=doc_type.type_code,
        type_confidence=doc_type.confidence,
        image_suggestions=len(info.suggestions),
        existing_images=info.existing_images,
    )
    d = score.as_dict()
    return {
        "name": path.name,
        "doc_type": doc_type.type_code,
        "total": d["total"],
        "passed": d["passed"],
        "dims": aggregate_dimensions(d["items"]),
        "items": d["items"],
    }


def measure_golden_dir(golden_dir: Path) -> list[dict[str, Any]]:
    if not golden_dir.exists():
        return []
    results = []
    for p in sorted(golden_dir.glob("*.docx")):
        if p.name.startswith("~$"):  # Word 잠금 임시파일 제외
            continue
        try:
            results.append(measure_docx(p))
        except Exception as e:  # noqa: BLE001 — 1건 실패가 전체를 안 깨게
            print(f"[WARN] 채점 실패 {p.name}: {e}")
    return results


def run_pytest() -> dict[str, int] | None:
    """tests/ 전체를 현재 인터프리터로 실행해 passed/failed 를 파싱."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(_APP_DIR), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    m_pass = _PYTEST_PASSED_RE.search(tail)
    m_fail = _PYTEST_FAILED_RE.search(tail)
    if not m_pass and not m_fail:
        print("[WARN] pytest 결과 파싱 실패 — 마지막 출력:")
        print("\n".join(tail.strip().splitlines()[-5:]))
        return None
    return {
        "passed": int(m_pass.group(1)) if m_pass else 0,
        "failed": int(m_fail.group(1)) if m_fail else 0,
    }


def main(argv: list[str] | None = None) -> int:
    _fix_console()
    ap = argparse.ArgumentParser(description="품질 게이트 기준선/시계열 갱신 (ratchet)")
    ap.add_argument("--golden-dir", default=str(DEFAULT_GOLDEN),
                    help=f"골든 문서 폴더(*.docx). 기본 {DEFAULT_GOLDEN}")
    ap.add_argument("--skip-tests", action="store_true", help="pytest 축 생략(문서 채점만)")
    ap.add_argument("--run", default=None, help="실행 라벨(기본=오늘 날짜)")
    ap.add_argument("--seed", action="store_true", help="기준선 강제 재시딩")
    args = ap.parse_args(argv)

    run_label = args.run or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    docs = measure_golden_dir(Path(args.golden_dir))
    tests = None if args.skip_tests else run_pytest()
    if not docs and tests is None:
        print(f"[SKIP] 측정할 것 없음 — 골든 문서 0건({args.golden_dir}) + 테스트 생략/파싱실패.")
        return 0

    summary = build_summary(docs, tests, run_label)

    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS / run_label
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    result = gate(summary, baseline, now, seed=args.seed)
    BASELINE.write_text(
        json.dumps(result.baseline_out, ensure_ascii=False, indent=2), encoding="utf-8")

    new_file = not TREND.exists()
    with TREND.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(TREND_HEADER)
        w.writerow(build_trend_row(summary))

    dims = summary["dims_avg"]
    print(f"[baseline] {result.status}")
    print(f"[KPI] 문서 {summary['n_docs']}건 avg={summary['avg_total']} "
          f"(서식 {dims['formatting']} / 위치·구조 {dims['placement']} / 이미지 {dims['image']}) "
          f"tests={tests}")
    print(f"[out] {BASELINE} / {TREND.name} / runs/{run_label}/summary.json")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
