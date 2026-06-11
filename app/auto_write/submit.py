"""제출용 사업계획서 자동 생성 CLI (end-to-end).

사용 (PowerShell):
  cd D:\auto_write\app
  python -m auto_write.submit --project <project_id> --announcement-file "공고.txt"
  python -m auto_write.submit --project <project_id> --announcement "..." --target 95
  python -m auto_write.submit --project <project_id> --no-images

전제: 먼저 양식 분석 + 프로젝트 생성 + 폼 저장이 끝난 project_id 가 있어야 한다
(웹 UI 또는 기존 흐름). 본 CLI 는 그 project_id 로 generate->평가루프->마감->품질->이미지를
한 번에 수행해 '제출초안' DOCX 를 만든다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ensure_directories, get_settings
from .services.evaluation_service import EvaluationService
from .services.evidence_service import EvidenceService
from .services.image_service import ImageService
from .services.openai_client import OpenAIService
from .services.project_service import ProjectService
from .services.qa_service import QAService
from .services.render_service import RenderService
from .services.submission_orchestrator import SubmissionPipeline
from .storage import Storage


def _make():
    settings = get_settings()
    ensure_directories(settings)
    storage = Storage(settings)
    oa = OpenAIService(settings)
    project_service = ProjectService(
        storage, oa, EvidenceService(oa), ImageService(oa), RenderService(), QAService()
    )
    evaluation_service = EvaluationService(oa)
    return settings, storage, project_service, evaluation_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="제출용 사업계획서 자동 생성 (end-to-end)")
    parser.add_argument("--project", required=True, help="대상 project_id")
    parser.add_argument("--announcement", default="", help="공고문 텍스트")
    parser.add_argument("--announcement-file", default="", help="공고문 파일 경로(txt/docx/pdf)")
    parser.add_argument("--target", type=int, default=92, help="공고 평가 목표 점수(기본 92)")
    parser.add_argument("--max-iter", type=int, default=3, help="평가 보완 최대 반복(기본 3)")
    parser.add_argument("--no-images", action="store_true", help="이미지(PNG) 삽입 비활성")
    parser.add_argument(
        "--no-notebooklm", action="store_true",
        help="NotebookLM 슬라이드 프롬프트 삽입 비활성(기본: 삽입함)",
    )
    parser.add_argument("--fill-plan-dir", default="", help="양식별 fill_plan.json 디렉터리")
    parser.add_argument("--no-acceptance", action="store_true",
                        help="실사용 수용검사 게이트(DRAFT 마킹) 생략")
    args = parser.parse_args(argv)

    settings, storage, project_service, evaluation_service = _make()

    ann = (args.announcement or "").strip()
    if not ann and args.announcement_file:
        p = Path(args.announcement_file)
        if p.exists():
            try:
                ann = project_service.extract_reference_text(p)
            except Exception:
                ann = p.read_text(encoding="utf-8", errors="ignore")

    pipeline = SubmissionPipeline(project_service, evaluation_service, storage, settings)
    report = pipeline.run(
        args.project,
        ann,
        target_score=args.target,
        max_iterations=args.max_iter,
        enable_images=not args.no_images,
        enable_notebooklm=not args.no_notebooklm,
        fill_plan_dir=(args.fill_plan_dir or None),
        acceptance_gate=not args.no_acceptance,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n최종 제출초안:", report.get("final_docx", ""))
    acc = report.get("acceptance") or {}
    if acc:
        print(f"수용검사: {acc.get('verdict', '')} (fail {acc.get('fail_defects', 0)}건)")
    if report.get("acceptance_error"):
        print(f"수용검사 실행 실패(판정 불가 — 제출 금지): {report['acceptance_error']}")
    if report.get("draft_mark_error"):
        print(f"_DRAFT 마킹 실패 — 파일명 직접 변경 전 제출 금지: {report['draft_mark_error']}")
    if report.get("needs_input"):
        print("[보완 필요 - 근거 부족, 직접 입력 권장]:", ", ".join(report["needs_input"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
