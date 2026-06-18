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
    parser.add_argument("--blind-review", action="store_true",
                        help="블라인드 공고 모드 — ○○○ 마스킹 허용 + 실명 잔존 검출(fail)")
    parser.add_argument("--required-format", default=None,
                        help="공고 요구 산출 형식(예: hwp) — 다르면 제출명 차단(_DRAFT)+변환 안내")
    parser.add_argument("--strict", action="store_true",
                        help="종료코드 계약 활성: 0=제출가능/1=입력오류/2=제출불가/3=검사불능 (기본은 항상 0)")
    parser.add_argument("--submit-clean", action="store_true",
                        help="게이트 직전 NotebookLM 프롬프트를 md 로 보존 후 블록 제거 — 통과 시 _제출용 명명")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="본문 분량 제한(p) — 초과 시 수용검사 warn(예: 15). 미지정=검사 안 함")
    parser.add_argument("--ai-section-max", type=int, default=None,
                        help="AI활용계획 등 섹션 분량 제한(p, 예: 2). 미지정=검사 안 함")
    args = parser.parse_args(argv)

    settings, storage, project_service, evaluation_service = _make()

    ann, ann_warn = _read_announcement(
        args.announcement, args.announcement_file, project_service.extract_reference_text
    )
    if ann_warn:
        # PIPE-7: 공고 파일 오타/부재를 침묵하지 않는다 — 평가 루프 생략을 명시 경고
        print(f"[경고] {ann_warn}")
        if args.strict:
            return 1

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
        blind_review=args.blind_review,
        required_format=args.required_format,
        submit_clean=args.submit_clean,
        max_pages=args.max_pages,
        ai_section_max=args.ai_section_max,
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
    if args.strict:
        # 종료코드 4분류(ralplan v2 P2): 검사불능(환경) > 문서 결함 순으로 판정
        if report.get("acceptance_error") or report.get("draft_mark_error"):
            return 3
        if (acc and not acc.get("submittable")) or report.get("format_mismatch"):
            return 2
    return 0


def _read_announcement(announcement: str, announcement_file: str, extract) -> tuple[str, str]:
    """공고 텍스트 로드 — (텍스트, 경고) 반환. 파일 부재/추출 실패를 침묵하지 않는다(PIPE-7)."""
    ann = (announcement or "").strip()
    if ann or not announcement_file:
        return ann, ""
    p = Path(announcement_file)
    if not p.exists():
        return "", f"공고 파일을 찾을 수 없음: {p} — 공고 평가 루프가 통째로 생략됩니다."
    try:
        return extract(p), ""
    except Exception:
        try:
            return p.read_text(encoding="utf-8", errors="ignore"), ""
        except Exception as exc:
            return "", f"공고 파일 읽기 실패({type(exc).__name__}) — 평가 루프 생략: {p}"


if __name__ == "__main__":
    raise SystemExit(main())
