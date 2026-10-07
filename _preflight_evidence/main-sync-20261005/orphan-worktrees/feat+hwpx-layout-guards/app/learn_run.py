"""learn_run.py — auto_write 자가학습 레이어 CLI 진입점.

사용 (PowerShell)
-----------------
cd D:\\auto_write\\app
py -3.11 learn_run.py --final-file "results\\제출본.docx"
py -3.11 learn_run.py --final-file 제출본.docx --project-id p1 --program-name "인천 시제품" ^
    --eval-report eval.json --quality-report q.json --blind-review

흐름
----
1) --final-file 존재 확인(없으면 exit 1)
2) 수용검사: .docx 만 run_acceptance 실행. .hwpx/.hwp 는 절대 호출하지 않는다(§9 F3)
   — 그 결과 verdict 는 "미검사"가 되고 exit 3 이다(F2, 절대 0/2 아님).
3) build_run_record 로 학습 레코드 조립(읽기 전용)
4) .docx 이면서 검사 성공했을 때만 classify_check 로 결함 분류(반복 통계로 code_improvement 승격)
5) 저장(runs.jsonl/defects.jsonl) → learning_report.md 생성 → plan_candidates(selfdev_candidates.jsonl)
   — 이 저장 단계들은 전부 부수효과라 개별 try/except 로 감싸고 경고만 남긴다(§9 M3).
   판정 종료코드는 4)까지의 결과로 이미 확정되며 저장 성공 여부와 무관하게 그대로 반환한다.

종료코드 계약(self_diagnose.py 와 동일): 0=제출가능 / 1=입력오류 / 2=제출불가 / 3=검사불능(미검사 포함)
읽기 전용 — 원본 문서를 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from auto_write.services.defect_classifier import classify_check
from auto_write.services.learning_report import write_learning_report
from auto_write.services.learning_store import LEARNING_ROOT, append_defect, append_run, load_defect_stats
from auto_write.services.run_evaluator import build_run_record
from auto_write.services.self_improvement_planner import plan_candidates
from auto_write.services.usage_acceptance import AcceptanceConfig, AcceptanceReport, run_acceptance

_DOCX_EXT = ".docx"


def _load_json_report(path_str: str | None) -> dict | None:
    if not path_str:
        return None
    p = Path(path_str)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[경고] 리포트 JSON 로드 실패({p}): {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    # ENC-1 과 동일 함정: cp949 콘솔에서 한글/이모지 출력이 죽지 않게 utf-8 강제.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="자가학습 레이어 실행 기록 (읽기 전용 + 학습저장소 신규 기록)")
    ap.add_argument("--final-file", required=True, help="평가할 최종 산출 파일(.docx/.hwpx/.hwp)")
    ap.add_argument("--project-id", default="")
    ap.add_argument("--program-name", default="")
    ap.add_argument("--eval-report", default=None, help="evaluation_service/eval_loop_runner 산출 JSON 경로")
    ap.add_argument("--quality-report", default=None, help="document_quality_orchestrator 산출 JSON 경로")
    ap.add_argument("--submission-report", default=None, help="auto_write.submit 산출 JSON 경로")
    ap.add_argument("--blind-review", action="store_true",
                    help="블라인드 공고 모드 — ○○○ 마스킹 허용 + 실명 잔존 검출(fail)")
    ap.add_argument("--strict-acceptance", action="store_true",
                    help="US-3c 선도입 warn 3종(괄호선택란·라벨변형·빈그림칸)을 fail 로 승격")
    ap.add_argument("--max-pages", type=int, default=None, help="본문 분량 제한(p)")
    ap.add_argument("--ai-section-max", type=int, default=None, help="AI활용계획 등 섹션 분량 제한(p)")
    ap.add_argument("--out-dir", default=None,
                    help="learning_report.md 저장 폴더(기본: workspace/learning)")
    args = ap.parse_args(argv)

    src = Path(args.final_file)
    if not src.exists():
        print(f"[오류] 파일 없음: {src}")
        return 1

    is_docx = src.suffix.lower() == _DOCX_EXT
    config = AcceptanceConfig(
        blind_review=args.blind_review,
        max_pages=args.max_pages,
        ai_section_max=args.ai_section_max,
        strict_acceptance=args.strict_acceptance,
    )

    acceptance_report: AcceptanceReport | None = None
    acceptance_error: str | None = None
    if is_docx:
        try:
            acceptance_report = run_acceptance(src, config)
        except Exception as exc:  # noqa: BLE001 — 검사기 실패는 '판정 불가'로 흡수(fail-closed)
            acceptance_error = f"{type(exc).__name__}: {exc}"
    # .hwpx/.hwp: run_acceptance 를 호출하지 않는다(§9 F3) — 미검사로 남는다.

    eval_report = _load_json_report(args.eval_report)
    quality_report = _load_json_report(args.quality_report)
    submission_report = _load_json_report(args.submission_report)

    run_record = build_run_record(
        src,
        project_id=args.project_id,
        program_name=args.program_name,
        acceptance=acceptance_report,
        acceptance_config=config,
        eval_report=eval_report,
        quality_report=quality_report,
        submission_report=submission_report,
    )
    if acceptance_error:
        run_record["verdict"] = "검사불능"
        run_record["acceptance_error"] = acceptance_error

    # §9 F2 (필수, fail-closed): exit 0 은 '실제 acceptance 리포트가 존재하고
    # submittable==True' 일 때만. 미검사/검사불능/그 외 전부 exit 3 — 절대 0 금지.
    if acceptance_error:
        exit_code = 3
    elif is_docx and acceptance_report is not None:
        exit_code = 0 if acceptance_report.submittable else 2
    else:
        exit_code = 3

    # --- 결함 분류(§9 F3: DOCX 전용, HWPX/HWP 는 분류하지 않는다) ---
    classified: list[dict] = []
    if is_docx and acceptance_report is not None:
        try:
            stats = load_defect_stats(last_n_runs=5, root=LEARNING_ROOT)
        except Exception:  # noqa: BLE001 — 통계 조회 실패는 반복승격 0 취급(안전한 기본값)
            stats = {}
        for result in acceptance_report.results:
            if result.passed:
                continue
            repeat_count = stats.get(result.check_id, {}).get("count", 0)
            classified.append(classify_check(result, repeat_count=repeat_count, doc_name=args.final_file))

    print(f"\n=== 자가학습 실행 기록: {src.name} ===")
    print(f"run_id: {run_record.get('run_id')}  판정: {run_record.get('verdict')}")
    scores = run_record.get("scores") or {}
    print(
        f"acceptance fail={scores.get('acceptance_fail')} warn={scores.get('acceptance_warn')} "
        f"eval={scores.get('eval_score')} quality={scores.get('quality_score')}"
    )
    if classified:
        print(f"결함 분류 {len(classified)}건:")
        for c in classified:
            print(f"  [{c['category']}] {c['check_id']} ({c['defects']}건) — {c['next_action']}")

    # --- 저장 (부수효과 — 개별 try/except, 판정 종료코드는 이미 위에서 확정됨: §9 M3) ---
    try:
        run_path = append_run(run_record, root=LEARNING_ROOT)
        print(f"\n저장: {run_path}")
    except (OSError, TypeError, ValueError) as exc:
        print(f"[경고] runs.jsonl 저장 실패: {type(exc).__name__}: {exc}", file=sys.stderr)

    for item in classified:
        try:
            append_defect({
                "run_id": run_record.get("run_id", ""),
                "check_id": item["check_id"],
                "label": item["label"],
                "severity": item["severity"],
                "defects": item["defects"],
                "samples": item.get("samples", [])[:5],
                "category": item["category"],
                "next_action": item["next_action"],
                "resolved": False,
                "created_at": run_record.get("created_at", ""),
            }, root=LEARNING_ROOT)
        except (OSError, TypeError, ValueError) as exc:
            print(
                f"[경고] defects.jsonl 저장 실패({item.get('check_id')}): {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    report_dir = Path(args.out_dir) if args.out_dir else LEARNING_ROOT
    try:
        report_path = write_learning_report(report_dir, run_record, classified)
        print(f"학습 리포트: {report_path}")
    except (OSError, ValueError) as exc:
        print(f"[경고] 학습 리포트 저장 실패: {type(exc).__name__}: {exc}", file=sys.stderr)

    try:
        candidates = plan_candidates(root=LEARNING_ROOT)
        if candidates:
            print(f"selfdev 후보 {len(candidates)}건 신규 등록됨(workspace/learning/selfdev_candidates.jsonl)")
    except (OSError, TypeError, ValueError) as exc:
        print(f"[경고] selfdev 후보 생성 실패: {type(exc).__name__}: {exc}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
